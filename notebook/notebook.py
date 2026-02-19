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
        nb.add_title("回测结果")
        nb.add_metrics(metrics_data)
        nb.add_line_chart(dates, [{'name': '净值', 'data': values}])
        nb.export_html("report.html")
        
        # Section 容器
        with nb.section("收益分析"):
            nb.add_metrics([...], title="核心指标")
            nb.add_line_chart(dates, series, title="净值曲线")
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
    
    def _add_cell(self, cell: Cell) -> 'Notebook':
        """添加单元格并返回self以支持链式调用"""
        self._cell_counter += 1
        if self._section_stack:
            self._section_stack[-1].cells.append(cell)
        else:
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
                nb.add_metrics([...], title="核心指标")
        """
        if level is None:
            level = len(self._section_stack) + 1
        return SectionContext(self, title, level)
    
    # ========== 标题和文本 ==========
    
    def add_title(self, text: str, level: int = 1) -> 'Notebook':
        """添加标题"""
        return self._add_cell(CellBuilder.title(text, level))
    
    def add_text(self, text: str, style: str = 'normal') -> 'Notebook':
        """添加文本"""
        return self._add_cell(CellBuilder.text(text, style))
    
    def add_markdown(self, text: str) -> 'Notebook':
        """添加Markdown内容"""
        return self._add_cell(CellBuilder.markdown(text))
    
    def add_divider(self) -> 'Notebook':
        """添加分隔线"""
        return self._add_cell(CellBuilder.divider())
    
    # ========== 代码 ==========
    
    def add_code(self, code: str, language: str = 'python', output: str = None) -> 'Notebook':
        """添加代码块"""
        return self._add_cell(CellBuilder.code(code, language, output))
    
    # ========== 表格 ==========
    
    def add_table(self, data: List[dict], columns: List[str] = None, 
                  title: str = None) -> 'Notebook':
        """添加表格"""
        return self._add_cell(CellBuilder.table(data, columns, title))
    
    def add_dataframe(self, df, title: str = None, columns: List[str] = None) -> 'Notebook':
        """添加DataFrame表格"""
        import pandas as pd
        if isinstance(df, pd.DataFrame):
            data = df.to_dict('records')
            cols = columns or list(df.columns)
        else:
            data = df
            cols = columns
        return self.add_table(data, cols, title)
    
    # ========== 指标卡片 ==========
    
    def add_metrics(self, data: List[dict], title: str = None, 
                    columns: int = 4) -> 'Notebook':
        """
        添加指标卡片
        
        data格式: [{'name': '指标名', 'value': '指标值', 'desc': '说明'}, ...]
        """
        return self._add_cell(CellBuilder.metrics(data, title, columns))
    
    # ========== 图表 ==========
    
    def add_chart(self, chart_type: str, data: dict, title: str = None,
                  height: int = 400, **options) -> 'Notebook':
        """添加图表（通用）"""
        return self._add_cell(CellBuilder.chart(chart_type, data, title, height, **options))
    
    def add_line_chart(self, dates: List, series: List[dict], 
                       title: str = None, **options) -> 'Notebook':
        """添加折线图"""
        return self._add_cell(CellBuilder.line_chart(dates, series, title, **options))
    
    def add_area_chart(self, dates: List, series: List[dict],
                       title: str = None, **options) -> 'Notebook':
        """添加面积图"""
        return self._add_cell(CellBuilder.area_chart(dates, series, title, **options))
    
    def add_bar_chart(self, categories: List, series: List[dict],
                      title: str = None, **options) -> 'Notebook':
        """添加柱状图"""
        return self._add_cell(CellBuilder.bar_chart(categories, series, title, **options))
    
    def add_pie_chart(self, data: List[dict], title: str = None,
                      **options) -> 'Notebook':
        """添加饼图"""
        return self._add_cell(CellBuilder.pie_chart(data, title, **options))
    
    def add_heatmap(self, data: dict, title: str = None, **options) -> 'Notebook':
        """添加热力图"""
        return self._add_cell(CellBuilder.heatmap(data, title, **options))
    
    def add_pyecharts(self, chart, title: str = None, height: int = 400, 
                      width: str = '100%') -> 'Notebook':
        """
        添加 pyecharts 图表
        
        Args:
            chart: pyecharts 图表对象（Kline, Line, Bar, Pie 等）
            title: 可选标题
            height: 图表高度（像素）
            width: 图表宽度（默认100%）
        
        Returns:
            Notebook: 支持链式调用
        """
        return self._add_cell(CellBuilder.pyecharts(chart, title, height, width))
    
    # ========== 权益曲线快捷方法 ==========
    
    def add_equity_curve(self, dates: List, values: List, 
                         title: str = '权益曲线',
                         benchmark_values: List = None) -> 'Notebook':
        """添加权益曲线图"""
        series = [{'name': '策略净值', 'data': values}]
        if benchmark_values:
            series.append({'name': '基准净值', 'data': benchmark_values})
        return self.add_line_chart(dates, series, title)
    
    def add_drawdown_chart(self, dates: List, drawdowns: List,
                           title: str = '回撤曲线') -> 'Notebook':
        """添加回撤曲线图"""
        series = [{'name': '回撤', 'data': drawdowns}]
        return self.add_area_chart(dates, series, title, color='#E94F37')
    
    def add_monthly_returns_heatmap(self, monthly_returns: dict,
                                    title: str = '月度收益热力图') -> 'Notebook':
        """
        添加月度收益热力图
        
        monthly_returns格式: {'2023': {'01': 0.05, '02': -0.02, ...}, ...}
        """
        return self.add_heatmap(monthly_returns, title)
    
    # ========== 可折叠区域 ==========
    
    def add_collapsible(self, title: str, cells: List[Cell],
                        collapsed: bool = True) -> 'Notebook':
        """添加可折叠区域"""
        return self._add_cell(CellBuilder.collapsible(title, cells, collapsed))
    
    def add_collapsible_table(self, title: str, data: List[dict],
                              columns: List[str] = None,
                              collapsed: bool = True) -> 'Notebook':
        """添加可折叠表格"""
        cell = CellBuilder.table(data, columns)
        return self.add_collapsible(title, [cell], collapsed)
    
    # ========== HTML ==========
    
    def add_html(self, html_content: str) -> 'Notebook':
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
        data_json = json.dumps(data, ensure_ascii=False, default=str)
        
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
