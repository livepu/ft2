from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Union
import json
import pandas as pd


# ========== 类型定义 ==========

class CellType(Enum):
    # 文本类
    TITLE = "title"
    TEXT = "text"
    MARKDOWN = "markdown"
    # 代码类
    CODE = "code"
    # 数据类
    TABLE = "table"
    METRICS = "metrics"
    # 图表类
    CHART = "chart"
    PYECHARTS = "pyecharts"
    # 布局类
    DIVIDER = "divider"
    HTML = "html"
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


CellLike = Union[Cell, 'Section']


# ========== 图表构建辅助函数 ==========

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


# ========== 图表注册表 ==========

CHART_REGISTRY = None

def _init_chart_registry():
    """延迟初始化图表注册表，避免 pyecharts 导入开销"""
    global CHART_REGISTRY
    if CHART_REGISTRY is not None:
        return
    
    from pyecharts.charts import Line, Bar, Pie, HeatMap, Kline, Scatter
    
    CHART_REGISTRY = {
        # ---------- 通用 XY 轴系列（统一处理）----------
        'line': {
            'class': Line,
            'builder': lambda data, opts: _build_xy_chart(Line, data, opts)
        },
        'bar': {
            'class': Bar,
            'builder': lambda data, opts: _build_xy_chart(Bar, data, opts)
        },
        'area': {
            'class': Line,
            'builder': lambda data, opts: _build_xy_chart(Line, data, opts, is_area=True)
        },
        'scatter': {
            'class': Scatter,
            'builder': lambda data, opts: _build_xy_chart(Scatter, data, opts)
        },
        'kline': {
            'class': Kline,
            'builder': lambda data, opts: _build_xy_chart(Kline, data, opts)
        },
        
        # ---------- 特殊类型（转换+构建合并）----------
        'pie': {
            'class': Pie,
            'builder': _build_pie
        },
        'heatmap': {
            'class': HeatMap,
            'builder': _build_heatmap
        },
    }


# ========== 通用构建器（XY 轴系列）----------

def _build_xy_chart(ChartClass, data, series_opts, is_area=False):
    """通用 XY 轴图表构建器（转换+构建合并）"""
    from pyecharts import options as opts
    chart = ChartClass()
    
    # 判断格式
    is_standard_format = isinstance(data, dict) and 'xAxis' in data and 'series' in data
    
    if not is_standard_format:
        # 处理非标准格式：{y: {x: v}} 或 DataFrame
        if isinstance(data, pd.DataFrame):
            df = data.copy()
        else:
            # 嵌套 dict 转 DataFrame
            df = pd.DataFrame(data)
        
        if isinstance(df.index, pd.RangeIndex) and len(df.columns) > 1:
            df = df.set_index(df.columns[0])
        x_axis = df.index.tolist()
        series_list = []
        for col in df.columns:
            series_list.append({
                'name': str(col),
                'data': df[col].tolist()
            })
        data = {
            'xAxis': x_axis,
            'series': series_list
        }
    
    chart.add_xaxis(data['xAxis'])
    for s in data['series']:
        params = {'series_name': s.get('name', ''), 'y_axis': s['data'], **series_opts}
        if is_area:
            params['areastyle_opts'] = opts.AreaStyleOpts(opacity=0.3)
        chart.add_yaxis(**params)
    return chart


# ========== 特殊构建器（转换+构建合并）----------

def _build_pie(data, series_opts):
    """饼图构建器（转换+构建合并）"""
    from pyecharts.charts import Pie
    chart = Pie()
    data_pair = [(item['name'], item['value']) for item in data]  # 转换
    chart.add('', data_pair, **series_opts)  # 构建
    return chart


def _build_heatmap(data, series_opts):
    """热力图构建器（转换+构建合并）"""
    from pyecharts.charts import HeatMap
    chart = HeatMap()
    
    # 统一转成 DataFrame
    if isinstance(data, pd.DataFrame):
        df = data.copy()
    else:
        df = pd.DataFrame(data)
    
    # 处理 RangeIndex
    if isinstance(df.index, pd.RangeIndex) and len(df.columns) > 1:
        df = df.set_index(df.columns[0])
    
    # 用 stack() 优化
    xaxis_data = [str(x) for x in df.index]
    yaxis_data = [str(y) for y in df.columns]
    
    x_map = {str(x): i for i, x in enumerate(df.index)}
    y_map = {str(y): i for i, y in enumerate(df.columns)}
    
    stacked = df.stack()
    values = [[x_map[str(x)], y_map[str(y)], v] for (x, y), v in stacked.items()]
    
    # 构建
    chart.add_xaxis(xaxis_data)
    chart.add_yaxis('', yaxis_data, values, **series_opts)
    return chart


# ========== Cell 构建器 ==========

class CellBuilder:
    """单元格构建器"""
    
    # 文本类
    
    @staticmethod
    def title(text: str, level: int = 1) -> Cell:
        return Cell(CellType.TITLE, text, options={"level": level})
    
    @staticmethod
    def text(text: str, style: str = 'normal') -> Cell:
        return Cell(CellType.TEXT, text, options={"style": style})
    
    @staticmethod
    def markdown(text: str) -> Cell:
        return Cell(CellType.MARKDOWN, text)
    
    # 代码类
    
    @staticmethod
    def code(code: str, language: str = 'python', output: str = None) -> Cell:
        return Cell(
            CellType.CODE,
            {"code": code, "language": language, "output": output}
        )
    
    # 数据类
    
    @staticmethod
    def table(data: List[Dict], columns: List[str] = None, options: dict = None) -> Cell:
        # 将字符串数组转换为对象数组格式
        # 输入: ["代码", "名称"]
        # 输出: [{"field": "代码", "title": "代码"}, {"field": "名称", "title": "名称"}]
        if columns:
            columns = [{"field": col, "title": col} for col in columns]
        
        opts = {"columns": columns} if columns else {}
        
        if options:
            opts.update(options)
        
        return Cell(CellType.TABLE, data, options=opts)
    
    @staticmethod
    def metrics(data: List[Dict], columns: int = 4) -> Cell:
        return Cell(CellType.METRICS, data, options={"columns": columns})
    
    # 图表类
    
    @staticmethod
    def chart(chart_type: str, data, height: str = '400px', **kwargs) -> Cell:
        width = kwargs.pop('width', '100%')
        
        # 1. 初始化注册表
        _init_chart_registry()
        
        # 2. 查表
        spec = CHART_REGISTRY.get(chart_type)
        if not spec:
            supported = list(CHART_REGISTRY.keys())
            raise ValueError(f"不支持的图表类型: {chart_type}，可用: {supported}")
        
        # 3. 提取参数
        global_opts_keys = ['title_opts', 'legend_opts', 'tooltip_opts',
                            'xaxis_opts', 'yaxis_opts', 'datazoom_opts',
                            'visualmap_opts', 'grid_opts']
        global_opts = {k: kwargs.pop(k) for k in global_opts_keys if k in kwargs}
        series_opts = kwargs.pop('series_opts', {})
        
        # 4. 构建图表
        chart = spec['builder'](data, series_opts)
        
        # 5. 全局配置
        if global_opts:
            chart.set_global_opts(**{k: _create_opts(k, v) for k, v in global_opts.items()})
        
        # 6. 输出
        option_dict = json.loads(chart.dump_options())
        return Cell(
            CellType.CHART,
            {"charts": option_dict, "width": width, "height": height}
        )
    
    @staticmethod
    def pyecharts(chart, height: str = '400px', width: str = '100%') -> Cell:
        option_dict = json.loads(chart.dump_options())
        
        return Cell(
            CellType.PYECHARTS,
            {
                "charts": option_dict,
                "width": width,
                "height": height
            }
        )
    
    # 布局类
    
    @staticmethod
    def divider() -> Cell:
        return Cell(CellType.DIVIDER, None)
    
    @staticmethod
    def html(html_content: str) -> Cell:
        return Cell(CellType.HTML, html_content)
    
    @staticmethod
    def section(title: str, children: List[CellLike] = None,
                level: int = 1, collapsed: bool = None) -> Section:
        opts = {"level": level}
        if collapsed is not None:
            opts["collapsed"] = collapsed
        return Section(children or [], title, opts)
