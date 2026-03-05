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


def _create_opts(opts_name: str, opts_dict: dict):
    """将 dict 转换为 pyecharts opts 对象"""
    from pyecharts import options as opts
    
    opts_map = {
        'title_opts': opts.TitleOpts,
        'legend_opts': opts.LegendOpts,
        'tooltip_opts': opts.TooltipOpts,
        'xaxis_opts': opts.AxisOpts,
        'yaxis_opts': opts.AxisOpts,
        'visualmap_opts': opts.VisualMapOpts,
        'grid_opts': opts.GridOpts,
    }
    
    if opts_name == 'datazoom_opts':
        return [opts.DataZoomOpts(**item) for item in opts_dict]
    
    OptClass = opts_map.get(opts_name)
    return OptClass(**opts_dict) if OptClass else opts_dict


def _build_line_bar_area(chart_type: str, data: dict, series_opts: dict):
    """构建 line/bar/area 图表"""
    from pyecharts.charts import Line, Bar
    from pyecharts import options as opts
    
    ChartClass = Line if chart_type in ('line', 'area') else Bar
    chart = ChartClass()
    
    chart.add_xaxis(data['xAxis'])
    
    for s in data['series']:
        params = {
            'series_name': s.get('name', ''),
            'y_axis': s['data'],
            **series_opts
        }
        if chart_type == 'area':
            params['areastyle_opts'] = opts.AreaStyleOpts(opacity=0.3)
        chart.add_yaxis(**params)
    
    return chart


def _build_pie(data: list, series_opts: dict):
    """构建饼图"""
    from pyecharts.charts import Pie
    
    chart = Pie()
    data_pair = [(item['name'], item['value']) for item in data]
    chart.add(series_name='', data_pair=data_pair, **series_opts)
    return chart


def _build_heatmap(data, series_opts: dict):
    """构建热力图"""
    from pyecharts.charts import HeatMap
    
    chart = HeatMap()
    
    if HAS_PANDAS and isinstance(data, pd.DataFrame):
        df = data.copy()
        if isinstance(df.index, pd.RangeIndex) and len(df.columns) > 1:
            df = df.set_index(df.columns[0])
        data = df.to_dict(orient='index')
    
    xaxis_data = []
    yaxis_data = []
    values = []
    
    for y_idx, (y_name, x_dict) in enumerate(data.items()):
        yaxis_data.append(str(y_name))
        for x_name, value in x_dict.items():
            x_name_str = str(x_name)
            if x_name_str not in xaxis_data:
                xaxis_data.append(x_name_str)
            values.append([xaxis_data.index(x_name_str), y_idx, value])
    
    chart.add_xaxis(xaxis_data)
    chart.add_yaxis(
        series_name='',
        yaxis_data=yaxis_data,
        value=values,
        **series_opts
    )
    
    return chart


def _build_kline(data: dict, series_opts: dict):
    """构建 K 线图"""
    from pyecharts.charts import Kline
    
    chart = Kline()
    chart.add_xaxis(data['xAxis'])
    
    for s in data['series']:
        chart.add_yaxis(
            series_name=s.get('name', ''),
            y_axis=s['data'],
            **series_opts
        )
    
    return chart


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
    def chart(chart_type: str, data, title: str, height: str = '400px', **kwargs) -> Cell:
        """
        创建图表（pyecharts 简化封装）
        
        Args:
            chart_type: 'line' | 'bar' | 'area' | 'pie' | 'heatmap' | 'kline'
            data: 图表数据（简化格式）
            title: Cell 标题（必填）
            height: 容器高度，默认 '400px'
            **kwargs: pyecharts 可选参数
        """
        width = kwargs.pop('width', '100%')
        
        global_opts_keys = ['title_opts', 'legend_opts', 'tooltip_opts',
                            'xaxis_opts', 'yaxis_opts', 'datazoom_opts',
                            'visualmap_opts', 'grid_opts']
        global_opts = {k: kwargs.pop(k) for k in global_opts_keys if k in kwargs}
        
        series_opts = kwargs.pop('series_opts', {})
        
        if chart_type in ('line', 'bar', 'area'):
            chart = _build_line_bar_area(chart_type, data, series_opts)
        elif chart_type == 'pie':
            chart = _build_pie(data, series_opts)
        elif chart_type == 'heatmap':
            chart = _build_heatmap(data, series_opts)
        elif chart_type == 'kline':
            chart = _build_kline(data, series_opts)
        else:
            raise ValueError(f"不支持的图表类型: {chart_type}")
        
        if global_opts:
            chart.set_global_opts(**{
                k: _create_opts(k, v) for k, v in global_opts.items()
            })
        
        option_dict = json.loads(chart.dump_options())
        
        return Cell(
            CellType.CHART,
            {"charts": option_dict, "width": width, "height": height},
            title
        )
    
    @staticmethod
    def line_chart(xaxis: List, series: List[Dict], title: str, height: str = '400px', **kwargs) -> Cell:
        return CellBuilder.chart('line', {"xAxis": xaxis, "series": series}, title, height, **kwargs)
    
    @staticmethod
    def area_chart(xaxis: List, series: List[Dict], title: str, height: str = '400px', **kwargs) -> Cell:
        return CellBuilder.chart('area', {"xAxis": xaxis, "series": series}, title, height, **kwargs)
    
    @staticmethod
    def bar_chart(xaxis: List, series: List[Dict], title: str, height: str = '400px', **kwargs) -> Cell:
        return CellBuilder.chart('bar', {"xAxis": xaxis, "series": series}, title, height, **kwargs)
    
    @staticmethod
    def pie_chart(data: List[Dict], title: str, height: str = '400px', **kwargs) -> Cell:
        return CellBuilder.chart('pie', data, title, height, **kwargs)
    
    @staticmethod
    def heatmap(data: Union[Dict, Any], title: str, height: str = '400px', **kwargs) -> Cell:
        return CellBuilder.chart('heatmap', data, title, height, **kwargs)
    
    @staticmethod
    def kline_chart(xaxis: List, series: List[Dict], title: str, height: str = '400px', **kwargs) -> Cell:
        return CellBuilder.chart('kline', {"xAxis": xaxis, "series": series}, title, height, **kwargs)
    
    @staticmethod
    def divider() -> Cell:
        return Cell(CellType.DIVIDER, None)
    
    @staticmethod
    def html(html_content: str) -> Cell:
        return Cell(CellType.HTML, html_content)
    
    @staticmethod
    def pyecharts(chart, title: str = None, height: str = '400px', width: str = '100%') -> Cell:
        option_dict = json.loads(chart.dump_options())
        
        return Cell(
            CellType.PYECHARTS,
            {
                "charts": option_dict,
                "width": width,
                "height": height
            },
            title
        )
    
    @staticmethod
    def section(title: str, children: List[CellLike] = None,
                level: int = 1, collapsed: bool = None) -> Section:
        opts = {"level": level}
        if collapsed is not None:
            opts["collapsed"] = collapsed
        return Section(children or [], title, opts)
