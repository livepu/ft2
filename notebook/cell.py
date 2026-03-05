from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
import json

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
    HTML = "html"
    PYECHARTS = "pyecharts"
    SECTION = "section"


CONTAINER_TYPES = {CellType.SECTION}


@dataclass
class Cell:
    """原子类型 Cell"""
    type: CellType
    content: Any
    title: Optional[str] = None
    options: Dict = field(default_factory=dict)
    
    def to_dict(self) -> Dict:
        result = {"type": self.type.value, "content": self.content}
        if self.title is not None:
            result["title"] = self.title
        if self.options:
            result["options"] = self.options
        return result


@dataclass
class Section:
    """容器类型（Section）"""
    children: List[Union[Cell, 'Section']] = field(default_factory=list)
    title: Optional[str] = None
    options: Dict = field(default_factory=dict)
    
    @property
    def type(self) -> CellType:
        return CellType.SECTION
    
    def to_dict(self) -> Dict:
        result = {
            "type": "section",
            "children": [c.to_dict() for c in self.children]
        }
        if self.title is not None:
            result["title"] = self.title
        if self.options:
            result["options"] = self.options
        return result


CellLike = Union[Cell, Section]


class CellBuilder:
    """单元格构建器"""
    
    @staticmethod
    def title(text: str, level: int = 1) -> Cell:
        return Cell(CellType.TITLE, text, options={"level": level})
    
    @staticmethod
    def text(text: str, style: str = 'normal') -> Cell:
        return Cell(CellType.TEXT, text, options={"style": style})
    
    @staticmethod
    def markdown(text: str) -> Cell:
        return Cell(CellType.MARKDOWN, text)
    
    @staticmethod
    def code(code: str, language: str = 'python', output: str = None) -> Cell:
        return Cell(
            CellType.CODE,
            {"code": code, "language": language, "output": output}
        )
    
    @staticmethod
    def table(data: List[Dict], columns: List[str] = None,
              title: str = None, options: dict = None) -> Cell:
        opts = {"columns": columns} if columns else {}
        
        if options:
            freeze = options.get('freeze')
            if freeze is not None:
                if isinstance(freeze, int):
                    opts["freeze"] = {"left": freeze, "right": 0}
                else:
                    opts["freeze"] = freeze
            
            if 'page' in options:
                opts["page"] = options["page"]
        
        return Cell(CellType.TABLE, data, title, opts)
    
    @staticmethod
    def metrics(data: List[Dict], title: str = None, columns: int = 4) -> Cell:
        return Cell(CellType.METRICS, data, title, {"columns": columns})
    
    @staticmethod
    def chart(chart_type: str, data: Dict, title: str = None, **options) -> Cell:
        height = options.pop('height', 400)
        return Cell(
            CellType.CHART,
            {"chart_type": chart_type, "data": data},
            title,
            {"height": height, **options}
        )
    
    @staticmethod
    def line_chart(xaxis: List, series: List[Dict], title: str = None, **options) -> Cell:
        return CellBuilder.chart('line', {"xAxis": xaxis, "series": series}, title, **options)
    
    @staticmethod
    def area_chart(xaxis: List, series: List[Dict], title: str = None, **options) -> Cell:
        return CellBuilder.chart('area', {"xAxis": xaxis, "series": series}, title, **options)
    
    @staticmethod
    def bar_chart(xaxis: List, series: List[Dict], title: str = None, **options) -> Cell:
        return CellBuilder.chart('bar', {"xAxis": xaxis, "series": series}, title, **options)
    
    @staticmethod
    def pie_chart(data: List[Dict], title: str = None, **options) -> Cell:
        return CellBuilder.chart('pie', {"data": data}, title, **options)
    
    @staticmethod
    def heatmap(data: Union[Dict, Any], title: str = None, **options) -> Cell:
        content = data
        
        if HAS_PANDAS and isinstance(data, pd.DataFrame):
            df = data.copy()
            # DataFrame: 第一列作为Y轴，其余列作为X轴
            if isinstance(df.index, pd.RangeIndex) and len(df.columns) > 1:
                df = df.set_index(df.columns[0])
            content = df.to_dict(orient='index')
        
        return Cell(CellType.HEATMAP, content, title, options)
    
    @staticmethod
    def divider() -> Cell:
        return Cell(CellType.DIVIDER, None)
    
    @staticmethod
    def html(html_content: str) -> Cell:
        return Cell(CellType.HTML, html_content)
    
    @staticmethod
    def pyecharts(chart, title: str = None, **options) -> Cell:
        import json
        
        # 优先从 pyecharts 对象中读取尺寸
        # 外部参数可覆盖，参数类型与 pyecharts 一致：字符串（如 "400px"、"100%"）
        width = options.pop('width', None) or getattr(chart, 'width', '100%')
        height = options.pop('height', None) or getattr(chart, 'height', '400px')
        
        # dump_options() 返回 JSON 字符串，需要解析为 Python 对象
        option_dict = json.loads(chart.dump_options())
        
        return Cell(
            CellType.PYECHARTS,
            {
                "option": option_dict,
                "width": width,
                "height": height
            },
            title,
            options
        )
    
    @staticmethod
    def section(title: str, children: List[CellLike] = None,
                level: int = 1, collapsed: bool = None) -> Section:
        opts = {"level": level}
        if collapsed is not None:
            opts["collapsed"] = collapsed
        return Section(children or [], title, opts)
