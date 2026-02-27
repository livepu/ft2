from typing import List, Optional, Union
from pathlib import Path
from datetime import datetime
import json
from jinja2 import Environment, FileSystemLoader

from .cell import Cell, CellType, CellBuilder


class SectionContext:
    """Section 上下文管理器"""
    
    def __init__(self, notebook: 'Notebook', title: str, level: int = 1):
        self.notebook = notebook
        self.title = title
        self.level = level
        self.cells: List[Cell] = []
    
    def __enter__(self) -> 'Notebook':
        self.notebook._push_section(self)
        return self.notebook
    
    def __exit__(self, exc_type, exc_val, exc_tb) -> bool:
        section_cell = CellBuilder.section(self.title, self.cells, self.level)
        self.notebook._pop_section()
        self.notebook._add_cell(section_cell)
        return False


class Notebook:
    """
    Notebook风格输出类
    
    使用方式：
        nb = Notebook("策略分析报告")
        nb.title("回测结果")
        nb.table(data, columns=['code', 'name'], freeze=2)
        nb.metrics([{'name': '收益率', 'value': '15%'}])
        nb.chart('line', {'dates': dates, 'series': series})
        nb.export_html("report.html")
        
        # Section 容器
        with nb.section("收益分析"):
            nb.metrics([...], title="核心指标")
            nb.chart('line', {'dates': dates, 'series': series}, title="净值曲线")
    """
    
    def __init__(self, title: str = "Notebook Report"):
        self.title = title
        self.cells: List[Cell] = []
        self.created_at = datetime.now()
        self._cell_counter = 0
        self._section_stack: List[SectionContext] = []
    
    def _push_section(self, section: SectionContext):
        """进入 Section"""
        self._section_stack.append(section)
    
    def _pop_section(self) -> SectionContext:
        """退出 Section"""
        return self._section_stack.pop()
    
    def _add_cell(self, cell: Cell, title: str = None) -> 'Notebook':
        """
        添加单元格并返回self以支持链式调用

        逻辑:
        1. 如果在 with 内 -> 添加到当前 Section（Cell 保留 title 作为小标题）
        2. 如果不在 with 内但有 title -> 自动创建 Section（Cell 清空 title，避免重复）
        3. 如果不在 with 内且无 title -> 普通 Cell 添加到顶层
        """
        self._cell_counter += 1

        if self._section_stack:
            # 在 with 内：添加到当前 Section，Cell 保留 title
            self._section_stack[-1].cells.append(cell)
        elif title:
            # 不在 with 内但有 title：自动创建 Section，Cell 清空 title 避免重复
            cell.title = None
            section_cell = CellBuilder.section(title, [cell], level=1)
            self.cells.append(section_cell)
        else:
            # 不在 with 内且无 title：普通 Cell
            self.cells.append(cell)

        return self
    
    def section(self, title: str, level: int = None) -> SectionContext:
        """
        创建 Section 容器（上下文管理器）
        
        Args:
            title: Section 标题
            level: 层级（自动计算）
        
        Returns:
            SectionContext: 上下文管理器
        
        Usage:
            with nb.section("收益分析"):
                nb.metrics([...], title="核心指标")
        """
        if level is None:
            level = len(self._section_stack) + 1
        return SectionContext(self, title, level)
    
    # ========== 标题和文本 ==========
    
    def title(self, text: str, level: int = 1) -> 'Notebook':
        """添加标题"""
        return self._add_cell(CellBuilder.title(text, level))
    
    def text(self, text: str, style: str = 'normal') -> 'Notebook':
        """添加文本"""
        return self._add_cell(CellBuilder.text(text, style))
    
    def markdown(self, text: str) -> 'Notebook':
        """添加Markdown内容"""
        return self._add_cell(CellBuilder.markdown(text))
    
    def divider(self) -> 'Notebook':
        """添加分隔线"""
        return self._add_cell(CellBuilder.divider())
    
    # ========== 代码 ==========
    
    def code(self, code: str, language: str = 'python', output: str = None) -> 'Notebook':
        """添加代码块"""
        return self._add_cell(CellBuilder.code(code, language, output))
    
    # ========== 表格 ==========
    
    def table(self, data, columns=None, title=None, **options):
        """
        添加表格
        
        核心参数:
            data: 表格数据（List[dict] 或 DataFrame）
                - List[dict]: [{'code': '000001', 'name': '基金A'}, ...]
                - DataFrame: pd.DataFrame 对象，自动转换
            columns: 列名列表（指定要显示的列及顺序）
                - ['code', 'name', 'type']  # 只显示这3列，按此顺序
                - None 时显示数据中的所有列
            title: 标题
                - '基金列表'
        
        可选参数 (**options):
            freeze: 冻结列配置
                - int: 冻结左侧 n 列
                - dict: {'left': n, 'right': m}
            page: 分页配置 {'limit': 20, 'limits': [10, 20, 50]}
            collapsed: 折叠状态
                - None: 普通表格（默认）
                - True: 可折叠表格，默认折叠
                - False: 可折叠表格，默认展开
        
        Examples:
            nb.table(data)
            nb.table(data, columns=['code', 'name'], title='基金列表')
            nb.table(df, title='数据表')  # DataFrame 自动识别
            nb.table(data, freeze=2)
            nb.table(data, freeze={'left': 2, 'right': 1})
            nb.table(data, title='详细数据', collapsed=True)
        """
        import pandas as pd
        
        if isinstance(data, pd.DataFrame):
            df_data = data.to_dict('records')
            cols = columns or list(data.columns)
        else:
            df_data = data
            cols = columns
        
        collapsed = options.get('collapsed')
        
        if collapsed is not None:
            cell = CellBuilder.table(df_data, cols, None, options)
            return self.collapsible(title, [cell], collapsed)
        else:
            return self._add_cell(CellBuilder.table(df_data, cols, title, options), title)
    
    # ========== 指标卡片 ==========
    
    def metrics(self, data: List[dict], title: str = None, columns: int = 4) -> 'Notebook':
        """
        添加指标卡片

        data格式: [{'name': '指标名', 'value': '指标值', 'desc': '说明'}, ...]
        """
        return self._add_cell(CellBuilder.metrics(data, title, columns), title)
    
    # ========== 图表 ==========
    
    def chart(self, chart_type, data=None, title=None, **options):
        """
        添加图表（统一入口）
        
        Args:
            chart_type: 图表类型
                - 'line': 折线图
                - 'area': 面积图
                - 'bar': 柱状图
                - 'pie': 饼图
                - 'heatmap': 热力图
                - pyecharts 对象: 直接传入，自动识别
            data: 图表数据（格式因类型而异）
                - line/area: {'dates': [...], 'series': [{'name': '', 'data': []}, ...]}
                - bar: {'categories': [...], 'series': [{'name': '', 'data': []}, ...]}
                - pie: [{'name': '', 'value': 0}, ...]
                - heatmap: {'2024': {'01': 0.05, ...}, ...}
            title: 标题
            **options: 可选参数
                - height: 高度（默认 400）
                - color: 颜色配置
                - 其他配置
        
        Examples:
            # 折线图
            nb.chart('line', {'dates': dates, 'series': series})
            
            # 柱状图
            nb.chart('bar', {'categories': categories, 'series': series})
            
            # 饼图
            nb.chart('pie', [{'name': '股票', 'value': 60}, ...])
            
            # 热力图
            nb.chart('heatmap', monthly_returns)
            
            # pyecharts 对象（自动识别）
            nb.chart(kline_chart)
        """
        # 自动识别 pyecharts 对象
        if hasattr(chart_type, 'dump_options'):
            height = options.get('height', 400)
            width = options.get('width', '100%')
            return self._add_cell(CellBuilder.pyecharts(chart_type, title, height, width), title)
        
        # 热力图单独处理
        if chart_type == 'heatmap':
            return self._add_cell(CellBuilder.heatmap(data, title, **options), title)
        
        # 普通图表
        height = options.get('height', 400)
        return self._add_cell(CellBuilder.chart(chart_type, data, title, height, **options), title)
    
    # ========== 可折叠区域 ==========
    
    def collapsible(self, title: str, cells: List[Cell],
                    collapsed: bool = True) -> 'Notebook':
        """添加可折叠区域"""
        return self._add_cell(CellBuilder.collapsible(title, cells, collapsed))
    
    # ========== HTML ==========
    
    def html(self, html_content: str) -> 'Notebook':
        """添加原始HTML"""
        return self._add_cell(CellBuilder.html(html_content))
    
    # ========== 输出 ==========
    
    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'title': self.title,
            'created_at': self.created_at.isoformat(),
            'cells': [cell.to_dict() for cell in self.cells]
        }
    
    def to_json(self) -> str:
        """导出为JSON"""
        return json.dumps(self.to_dict(), ensure_ascii=False, default=str)
    
    def export_html(self, output_path: str, template_path: str = None) -> str:
        """
        导出为HTML文件
        
        :param output_path: 输出文件路径
        :param template_path: 自定义模板路径
        :return: 输出文件路径
        """
        if template_path is None:
            template_dir = Path(__file__).parent.parent / 'template'
            template_path = str(template_dir / 'notebook.html')
        else:
            template_dir = Path(template_path).parent
            template_path = str(template_path)
        
        env = Environment(loader=FileSystemLoader(str(template_dir)))
        template = env.get_template(Path(template_path).name)
        
        data = {
            'title': self.title,
            'createdAt': self.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'cells': [cell.to_dict() for cell in self.cells]
        }
        data_json = json.dumps(data, ensure_ascii=False, default=str, indent=2)
        
        html_content = template.render(data_json=data_json)
        
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(html_content, encoding='utf-8')
        
        return str(output_path)
    
    def __repr__(self):
        return f"<Notebook '{self.title}' with {len(self.cells)} cells>"
    
    def __len__(self):
        return len(self.cells)
    
    def __getitem__(self, index):
        return self.cells[index]
