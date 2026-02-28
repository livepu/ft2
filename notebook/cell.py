from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
from datetime import datetime
import json

# 可选依赖：pandas
try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False


class CellType(Enum):
    TITLE = "title"
    TEXT = "text"
    MARKDOWN = "markdown"
    CODE = "code"
    TABLE = "table"
    METRICS = "metrics"
    CHART = "chart"
    HEATMAP = "heatmap"
    DIVIDER = "divider"
    COLLAPSIBLE = "collapsible"
    HTML = "html"
    PYECHARTS = "pyecharts"
    SECTION = "section"


@dataclass
class Cell:
    """单元格基类"""
    type: CellType
    content: Any
    title: Optional[str] = None
    options: Dict = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        result = {
            'type': self.type.value,
            'content': self.content,
            'title': self.title,
            'options': self.options,
        }
        if self.type == CellType.COLLAPSIBLE and isinstance(self.content, list):
            result['content'] = [c.to_dict() if isinstance(c, Cell) else c for c in self.content]
        if self.type == CellType.SECTION and isinstance(self.content, list):
            result['content'] = [c.to_dict() if isinstance(c, Cell) else c for c in self.content]
        return result


class CellBuilder:
    """单元格构建器 - 提供便捷的静态方法"""
    
    @staticmethod
    def title(text: str, level: int = 1) -> Cell:
        """创建标题单元格"""
        return Cell(
            type=CellType.TITLE,
            content=text,
            options={'level': level}
        )
    
    @staticmethod
    def text(text: str, style: str = 'normal') -> Cell:
        """创建文本单元格"""
        return Cell(
            type=CellType.TEXT,
            content=text,
            options={'style': style}
        )
    
    @staticmethod
    def markdown(text: str) -> Cell:
        """创建Markdown单元格"""
        return Cell(
            type=CellType.MARKDOWN,
            content=text
        )
    
    @staticmethod
    def code(code: str, language: str = 'python', output: str = None) -> Cell:
        """创建代码单元格"""
        return Cell(
            type=CellType.CODE,
            content={
                'code': code,
                'language': language,
                'output': output
            }
        )
    
    @staticmethod
    def table(data: List[Dict], columns: List[str] = None, title: str = None,
              options: dict = None) -> Cell:
        """
        创建表格单元格
        
        Args:
            data: 表格数据
            columns: 列名列表
            title: 标题
            options: 可选配置
                - freeze: 冻结列配置 (int 或 dict)
                    - int: 冻结左侧 n 列
                    - dict: {'left': n, 'right': m}
                - page: 分页配置 {'limit': 20, 'limits': [10, 20, 50]}
        """
        opts = {'columns': columns} if columns else {}
        
        if options:
            freeze = options.get('freeze')
            if freeze is not None:
                if isinstance(freeze, int):
                    opts['freeze'] = {'left': freeze, 'right': 0}
                else:
                    opts['freeze'] = freeze
            
            if 'page' in options:
                opts['page'] = options['page']
        
        return Cell(
            type=CellType.TABLE,
            content=data,
            title=title,
            options=opts
        )
    
    @staticmethod
    def metrics(data: List[Dict], title: str = None, columns: int = 4) -> Cell:
        """创建指标卡片单元格"""
        return Cell(
            type=CellType.METRICS,
            content=data,
            title=title,
            options={'columns': columns}
        )
    
    @staticmethod
    def chart(chart_type: str, data: Dict, title: str = None, **options) -> Cell:
        """创建图表单元格"""
        height = options.pop('height', 400)
        chart_options = {'height': height, **options}
        return Cell(
            type=CellType.CHART,
            content={
                'chart_type': chart_type,
                'data': data
            },
            title=title,
            options=chart_options
        )
    
    @staticmethod
    def line_chart(dates: List, series: List[Dict], title: str = None, **options) -> Cell:
        """创建折线图"""
        return CellBuilder.chart('line', {'dates': dates, 'series': series}, title, **options)
    
    @staticmethod
    def area_chart(dates: List, series: List[Dict], title: str = None, **options) -> Cell:
        """创建面积图"""
        return CellBuilder.chart('area', {'dates': dates, 'series': series}, title, **options)
    
    @staticmethod
    def bar_chart(categories: List, series: List[Dict], title: str = None, **options) -> Cell:
        """创建柱状图"""
        return CellBuilder.chart('bar', {'categories': categories, 'series': series}, title, **options)
    
    @staticmethod
    def pie_chart(data: List[Dict], title: str = None, **options) -> Cell:
        """创建饼图"""
        return CellBuilder.chart('pie', {'data': data}, title, **options)
    
    @staticmethod
    def heatmap(
        data: Union[Dict, Any], 
        title: str = None, 
        **options
    ) -> Cell:
        """
        创建热力图
        
        Args:
            data: 数据源，支持格式：
                - dict: 嵌套字典 {y: {x: value, ...}, ...}
                - DataFrame: 第一列作为Y轴，其余列作为X轴
            title: 标题
            **options: 其他配置
        
        Data Format:
            嵌套字典与DataFrame宽格式结构等价，可互转。
            
            例1：年月收益
            ─────────────────────────────────────────
            # dict 嵌套格式
            {
                '2023': {'1月': 0.02, '2月': -0.01, '3月': 0.03},
                '2024': {'1月': 0.05, '2月': -0.02, '3月': 0.08}
            }
            
            # DataFrame 格式（第一列=Y轴，其余列=X轴）
                年    1月    2月    3月
            0  2023  0.02  -0.01   0.03
            1  2024  0.05  -0.02   0.08
            
            例2：相关性矩阵（股票/策略 间的相关系数）
            ─────────────────────────────────────────
            # dict 嵌套格式
            {
                '茅台': {'茅台': 1.00, '平安': 0.35, '万科': 0.28},
                '平安': {'茅台': 0.35, '平安': 1.00, '万科': 0.52},
                '万科': {'茅台': 0.28, '平安': 0.52, '万科': 1.00}
            }
            
            # DataFrame 格式
                   茅台   平安   万科
            茅台  1.00  0.35  0.28
            平安  0.35  1.00  0.52
            万科  0.28  0.52  1.00
            
            相互转换：
                dict → DataFrame: pd.DataFrame.from_dict(data, orient='index')
                DataFrame → dict: df.set_index('第一列名').to_dict(orient='index')
        
        Examples:
            # 方式1：嵌套字典
            nb.heatmap({
                '2023': {'1月': 0.02, '2月': -0.01, '3月': 0.03},
                '2024': {'1月': 0.05, '2月': -0.02, '3月': 0.08}
            }, title='月度收益热力图')
            
            # 方式2：DataFrame（第一列=Y轴，其余列=X轴）
            df = pd.DataFrame({
                '年': ['2023', '2024'],
                '1月': [0.02, 0.05],
                '2月': [-0.01, -0.02],
                '3月': [0.03, 0.08]
            })
            nb.heatmap(df, title='月度收益热力图')
        """
        content = data
        
        # DataFrame 处理
        if HAS_PANDAS and isinstance(data, pd.DataFrame):
            df = data.copy()
            
            # 宽格式模式：第一列作为 Y轴，其余列作为 X轴
            # 如果index是默认数字索引(RangeIndex)，则将第一列设为index
            # 相关性矩阵等场景，index已设置好，无需处理
            if isinstance(df.index, pd.RangeIndex) and len(df.columns) > 1:
                df = df.set_index(df.columns[0])
            
            # 转换为嵌套字典
            content = df.to_dict(orient='index')
        
        return Cell(
            type=CellType.HEATMAP,
            content=content,
            title=title,
            options=options
        )
    
    @staticmethod
    def divider() -> Cell:
        """创建分隔线"""
        return Cell(type=CellType.DIVIDER, content=None)
    
    @staticmethod
    def collapsible(title: str, cells: List[Cell], collapsed: bool = True) -> Cell:
        """创建可折叠区域"""
        return Cell(
            type=CellType.COLLAPSIBLE,
            content=cells,
            title=title,
            options={'collapsed': collapsed}
        )
    
    @staticmethod
    def html(html_content: str) -> Cell:
        """创建HTML单元格"""
        return Cell(type=CellType.HTML, content=html_content)
    
    @staticmethod
    def pyecharts(chart, title: str = None, **options) -> Cell:
        """
        创建 pyecharts 图表单元格
        
        Args:
            chart: pyecharts 图表对象（Kline, Line, Bar, Pie 等）
            title: 可选标题
            **options: 可选参数
                - height: 图表高度（像素，默认400）
                - width: 图表宽度（默认100%）
        
        Returns:
            Cell: 封装后的单元格
        """
        height = options.pop('height', 400)
        width = options.pop('width', '100%')
        return Cell(
            type=CellType.PYECHARTS,
            content={
                'option': chart.dump_options(),
                'width': width,
                'height': f'{height}px'
            },
            title=title,
            options={'height': height, 'width': width}
        )
    
    @staticmethod
    def section(title: str, cells: List['Cell'] = None, level: int = 1) -> Cell:
        """
        创建 Section 容器
        
        Args:
            title: Section 标题
            cells: 子单元格列表
            level: 层级（用于样式）
        
        Returns:
            Cell: Section 单元格
        """
        return Cell(
            type=CellType.SECTION,
            content=cells or [],
            title=title,
            options={'level': level}
        )
