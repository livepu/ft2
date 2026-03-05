# PyEcharts V2.1 参数规范文档

基于 pyecharts 2.1.0 源码分析整理

## 1. 基础类型定义

```python
# series_options.py 中的基础类型
Numeric = Union[int, float]
JSFunc = Union[str, JsCode]  # JavaScript 函数
Sequence = list
Optional = Optional
Union = Union
```

### 1.1 数据类型规范

| 类型 | Python 形式 | 示例 |
|------|-------------|------|
| 尺寸 | `str` (带单位) | `"900px"`, `"100%"`, `"80vh"` |
| 颜色 | `str` (hex/rgba) | `"#fff"`, `"rgba(0,0,0,0.5)"` |
| 坐标 | `str` / `int` / `float` | `"center"`, `10`, `50%` |
| 布尔 | `bool` | `True`, `False` |
| 数值 | `int` / `float` | `1`, `1.5` |
| 百分比 | `str` | `"10%"`, `"50%"` |

---

## 2. 初始化配置项 (InitOpts)

图表创建时的初始配置，属于容器层配置

```python
from pyecharts import options as opts
from pyecharts.globals import ThemeType, RenderType

chart = Bar(init_opts=opts.InitOpts(
    width="900px",              # 容器宽度 (默认 "900px")
    height="500px",             # 容器高度 (默认 "500px")
    is_horizontal_center=False,  # 是否水平居中
    chart_id=None,              # 图表 DOM ID (自动生成)
    renderer=RenderType.CANVAS, # 渲染器: "canvas" / "svg"
    page_title="PyEcharts",      # HTML 页面标题
    theme=ThemeType.WHITE,      # 主题
    bg_color=None,              # 背景色 (str 或 dict)
    is_fill_bg_color=False,     # 是否填充背景色
    js_host="",                 # JS 文件 CDN 地址
    animation_opts=AnimationOpts(), # 动画配置
    aria_opts=AriaOpts(),       # 无障碍配置
))
```

### 2.1 主题类型 (ThemeType)

```python
from pyecharts.globals import ThemeType

ThemeType.WHITE       # 白色 (默认)
ThemeType.LIGHT       # 浅色
ThemeType.DARK       # 深色
ThemeType.CHALK      # 粉笔风
ThemeType.ESSOS     # 暗黑
ThemeType.INFOGRAPHIC # 信息图
ThemeType.MACARONS   # 马卡龙
ThemeType.PURPLE_PASSION # 紫罗兰
ThemeType.ROMA       # 罗马
ThemeType.ROMANTIC   # 浪漫
ThemeType.VINTAGE    # 复古
ThemeType.WALDEN     # 瓦尔登
ThemeType.WESTEROS   # 权游
ThemeType.WEY        # wey
```

### 2.2 渲染器类型 (RenderType)

```python
from pyecharts.globals import RenderType

RenderType.CANVAS  # Canvas 渲染 (默认)
RenderType.SVG    # SVG 渲染
```

---

## 3. 全局配置项 (Global Options)

通过 `set_global_opts()` 方法设置

### 3.1 标题配置项 (TitleOpts)

```python
chart.set_global_opts(
    title_opts=opts.TitleOpts(
        is_show=True,                # 是否显示
        title="主标题",              # 主标题
        title_link=None,             # 主标题链接
        title_target="blank",        # 主标题链接打开方式
        subtitle="副标题",           # 副标题
        subtitle_link=None,          # 副标题链接
        subtitle_target="blank",     # 副标题链接打开方式
        pos_left="center",           # 左侧位置
        pos_right=None,              # 右侧位置
        pos_top=None,                # 顶部位置
        pos_bottom=None,             # 底部位置
        padding=5,                   # 内边距
        item_gap=10,                 # 主副标题间距
        text_align="auto",           # 水平对齐
        text_vertical_align="auto",  # 垂直对齐
        title_textstyle_opts=TextStyleOpts(...),  # 标题文字样式
        subtitle_textstyle_opts=TextStyleOpts(...), # 副标题文字样式
    )
)
```

### 3.2 图例配置项 (LegendOpts)

```python
chart.set_global_opts(
    legend_opts=opts.LegendOpts(
        type_=None,                 # 图例类型: "plain" / "scroll"
        selected_mode=None,         # 选择模式: True / False / "single" / "multiple"
        is_show=True,               # 是否显示
        pos_left=None,              # 左侧位置
        pos_right=None,             # 右侧位置
        pos_top=None,               # 顶部位置
        pos_bottom=None,            # 底部位置
        orient="horizontal",        # 布局方向: "horizontal" / "vertical"
        align="auto",                # 对齐方式: "auto" / "left" / "right"
        padding=5,                   # 内边距
        item_gap=10,                # 间距
        item_width=25,              # 图例宽度
        item_height=14,             # 图例高度
        inactive_color="#ccc",      # 未选中颜色
        textstyle_opts=TextStyleOpts(...), # 文字样式
        legend_icon=None,           # 图例图标
        background_color="transparent",
        border_color="#ccc",
        border_width=None,
        border_radius=0,
        # 分页相关
        page_button_item_gap=5,
        page_button_gap=None,
        page_button_position="end",
        page_formatter="{current}/{total}",
        page_icon=None,
        page_icon_color="#2f4554",
        page_icon_inactive_color="#aaa",
        page_icon_size=15,
        is_page_animation=True,
        page_animation_duration_update=800,
        # 筛选器
        selector=False,
        selector_label=LabelOpts(...),
        selector_position="auto",
        selector_item_gap=7,
        selector_button_gap=10,
    )
)
```

### 3.3 提示框配置项 (TooltipOpts)

```python
chart.set_global_opts(
    tooltip_opts=opts.TooltipOpts(
        is_show=True,               # 是否显示
        trigger="item",             # 触发类型: "item" / "axis" / "none"
        trigger_on="mousemove|click", # 触发条件
        axis_pointer_type="line",   # 坐标轴指示器类型
        is_show_content=True,       # 是否显示提示框内容
        is_always_show_content=False, # 是否常显示
        show_delay=0,               # 显示延迟
        hide_delay=100,             # 隐藏延迟
        is_enterable=False,         # 鼠标是否可进入
        is_confine=False,           # 是否限制在容器内
        is_append_to_body=False,    # 是否添加到 body
        transition_duration=0.4,   # 动画过渡时间
        position=None,               # 位置
        formatter=None,             # 格式化函数
        value_formatter=None,       # 数值格式化
        background_color=None,      # 背景色
        border_color=None,          # 边框颜色
        border_width=0,             # 边框宽度
        padding=5,                  # 内边距
        textstyle_opts=TextStyleOpts(...), # 文字样式
        extra_css_text=None,        # 额外 CSS
        order="seriesAsc",          # 排序: "seriesAsc" / "seriesDesc"
    )
)
```

### 3.4 工具箱配置项 (ToolboxOpts)

```python
chart.set_global_opts(
    toolbox_opts=opts.ToolboxOpts(
        is_show=True,               # 是否显示
        orient="horizontal",       # 布局方向
        item_size=15,              # 工具大小
        item_gap=10,               # 间距
        pos_left="80%",            # 左侧位置
        pos_right=None,
        pos_top=None,
        pos_bottom=None,
        feature=ToolBoxFeatureOpts(
            save_as_image=ToolBoxFeatureSaveAsImageOpts(...),
            restore=ToolBoxFeatureRestoreOpts(...),
            data_view=ToolBoxFeatureDataViewOpts(...),
            data_zoom=ToolBoxFeatureDataZoomOpts(...),
            magic_type=ToolBoxFeatureMagicTypeOpts(...),
            brush=ToolBoxFeatureBrushOpts(...),
        ),
    )
)
```

### 3.5 坐标轴配置项 (AxisOpts)

```python
chart.set_global_opts(
    xaxis_opts=opts.AxisOpts(
        type_=None,               # 坐标轴类型: "value" / "category" / "time" / "log"
        name=None,                 # 坐标轴名称
        is_show=True,              # 是否显示
        is_scale=False,            # 是否为脱离 0 值
        is_inverse=False,          # 是否反向
        name_location="end",       # 名称位置
        name_gap=15,                # 名称与轴距离
        name_rotate=None,          # 名称旋转角度
        interval=None,             # 强制设置坐标轴分割间隔
        grid_index=None,           # 所属网格索引
        position=None,             # 位置
        offset=0,                  # 偏移量
        split_number=5,            # 分割段数
        boundary_gap=None,         # 边界间隙
        min_=None,                 # 最小值
        max_=None,                 # 最大值
        min_interval=0,            # 最小间隔
        max_interval=None,         # 最大间隔
        log_base=None,             # 对数底数
        is_silent=False,           # 是否禁用交互
        is_trigger_event=False,   # 是否触发事件
        axisline_opts=AxisLineOpts(...),     # 轴线配置
        axistick_opts=AxisTickOpts(...),      # 刻度配置
        axislabel_opts=LabelOpts(...),        # 标签配置
        axispointer_opts=AxisPointerOpts(...),# 指示器配置
        splitarea_opts=SplitAreaOpts(...),    # 分割区域配置
        splitline_opts=SplitLineOpts(...),    # 分割线配置
    ),
    yaxis_opts=opts.AxisOpts(...)
)
```

### 3.6 数据区域缩放配置项 (DataZoomOpts)

```python
chart.set_global_opts(
    datazoom_opts=[
        opts.DataZoomOpts(
            is_show=True,           # 是否显示
            type_="slider",         # 类型: "slider" / "inside"
            is_disabled=False,      # 是否禁用
            is_realtime=True,       # 实时更新
            is_show_detail=True,    # 显示细节
            is_show_data_shadow=True, # 显示数据阴影
            range_start=20,         # 起始位置 (%)
            range_end=80,           # 结束位置 (%)
            start_value=None,       # 起始值
            end_value=None,         # 结束值
            min_span=None,          # 最小缩放跨度
            max_span=None,          # 最大缩放跨度
            orient="horizontal",    # 方向
            xaxis_index=None,       # 控制的 x 轴
            yaxis_index=None,       # 控制的 y 轴
            is_zoom_lock=False,     # 锁定缩放
            pos_left=None,
            pos_right=None,
            pos_top=None,
            pos_bottom=None,
            filter_mode="filter",   # 过滤模式
        ),
        # inside 类型用于鼠标滚轮缩放
        opts.DataZoomOpts(
            type_="inside",
            xaxis_index=[0],
            is_zoom_on_mouse_wheel=True,
            is_move_on_mouse_move=True,
        )
    ]
)
```

### 3.7 视觉映射配置项 (VisualMapOpts)

```python
chart.set_global_opts(
    visualmap_opts=opts.VisualMapOpts(
        is_show=True,               # 是否显示
        type_="color",              # 类型: "color" / "size"
        min_=0,                     # 最小值
        max_=100,                   # 最大值
        range_=None,               # 选定范围
        range_text=None,            # 两端文字
        range_color=None,           # 颜色范围
        range_size=None,            # 大小范围
        orient="vertical",          # 方向
        pos_left=None,
        pos_right=None,
        pos_top=None,
        pos_bottom=None,
        split_number=5,            # 分段数
        is_piecewise=False,         # 是否分段
        is_inverse=False,           # 是否反向
        pieces=None,                # 自定义分段
        precision=None,             # 精度
        item_width=20,              # 宽度
        item_height=140,            # 高度
    )
)
```

### 3.8 网格配置项 (GridOpts)

```python
chart.set_global_opts(
    grid_opts=opts.GridOpts(
        is_show=False,              # 是否显示
        z_level=0,                  # z 层级
        z=2,                        # z 层级
        pos_left=None,              # 左侧位置
        pos_top=None,               # 顶部位置
        pos_right=None,             # 右侧位置
        pos_bottom=None,            # 底部位置
        width=None,                 # 宽度
        height=None,                # 高度
        is_contain_label=False,     # 是否包含标签
        background_color="transparent",
        border_color="#ccc",
        border_width=1,
    )
)
```

---

## 4. 系列配置项 (Series Options)

通过 `add_yaxis()` 等方法设置

### 4.1 标签配置项 (LabelOpts)

```python
bar.add_yaxis(
    "系列名",
    [1, 2, 3],
    label_opts=opts.LabelOpts(
        is_show=True,              # 是否显示
        position=None,             # 位置
        color=None,                # 颜色
        opacity=None,              # 透明度
        distance=None,             # 距离
        font_size=None,            # 字体大小
        font_style=None,           # 字体风格
        font_weight=None,          # 字体粗细
        font_family=None,          # 字体
        rotate=None,               # 旋转角度
        offset=None,               # 偏移
        margin=8,                 # 边距
        formatter=None,            # 格式化
        background_color=None,     # 背景色
        border_color=None,         # 边框颜色
        border_width=None,         # 边框宽度
        border_radius=0,           # 圆角
        overflow="none",           # 溢出处理
        rich=None,                 # 富文本
    )
)
```

**position 位置参数说明:**

| 图表类型 | 可选位置 |
|----------|----------|
| 通用 | `"top"`, `"left"`, `"right"`, `"bottom"` |
| 饼图 | `"outside"`, `"inside"`, `"inner"`, `"center"` |
| 散点图 | `["50%", "50%"]` (像素/百分比坐标) |
| K线图 | `"open"`, `"close"`, `"low"`, `"high"` |

### 4.2 图元样式配置项 (ItemStyleOpts)

```python
bar.add_yaxis(
    "系列名",
    [1, 2, 3],
    itemstyle_opts=opts.ItemStyleOpts(
        color=None,               # 主色
        color0=None,              # 备用色 (如 K 线下跌)
        border_color=None,        # 边框色
        border_color0=None,       # 备用边框色
        border_width=None,        # 边框宽度
        border_type=None,         # 边框类型: "solid" / "dashed" / "dotted"
        border_radius=0,          # 圆角
        opacity=None,             # 透明度
        area_color=None,          # 区域填充色
    )
)
```

### 4.3 线条样式配置项 (LineStyleOpts)

```python
line.add_yaxis(
    "系列名",
    [1, 2, 3],
    linestyle_opts=opts.LineStyleOpts(
        is_show=False,            # 是否显示
        width=1,                   # 线宽
        opacity=None,             # 透明度
        curve=0,                   # 曲线弯曲度 (0-1)
        type_="solid",             # 类型: "solid" / "dashed" / "dotted"
        color=None,                # 颜色
    )
)
```

### 4.4 面积样式配置项 (AreaStyleOpts)

```python
line.add_yaxis(
    "系列名",
    [1, 2, 3],
    areastyle_opts=opts.AreaStyleOpts(
        opacity=0,                # 透明度
        color=None,               # 颜色
        shadow_blur=None,         # 阴影模糊
        shadow_color=None,        # 阴影颜色
        shadow_offset_x=None,     # 阴影 X 偏移
        shadow_offset_y=None,     # 阴影 Y 偏移
    )
)
```

### 4.5 标记点配置项 (MarkPointOpts)

```python
bar.add_yaxis(
    "系列名",
    [1, 2, 3],
    markpoint_opts=opts.MarkPointOpts(
        data=[
            opts.MarkPointItem(
                name="最大值",
                type_="max",      # "max" / "min" / "average" / "median"
                value_index=None,
                value_dim=None,
                coord=None,       # 坐标 [x, y]
                x=None,
                y=None,
                value=None,
                symbol=None,      # 标记图标
                symbol_size=None, # 标记大小
                itemstyle_opts=ItemStyleOpts(...),
                label_opts=LabelOpts(...),
            ),
            opts.MarkPointItem(
                name="自定义点",
                coord=["A", 100], # 坐标
                value=100,
                symbol="pin",
                symbol_size=50,
            ),
        ],
        symbol="pin",             # 默认标记
        symbol_size=50,
        label_opts=LabelOpts(...),
    )
)
```

**MarkPoint 类型值:**

- `"max"` - 最大值
- `"min"` - 最小值
- `"average"` - 平均值
- `"median"` - 中位数
- `"start"` - 起点
- `"end"` - 终点

### 4.6 标记线配置项 (MarkLineOpts)

```python
bar.add_yaxis(
    "系列名",
    [1, 2, 3],
    markline_opts=opts.MarkLineOpts(
        is_silent=False,
        data=[
            opts.MarkLineItem(
                name="平均线",
                type_="average",   # "average" / "max" / "min"
                x="20%",
                y=None,
                coord=None,
                symbol=None,
                symbol_size=None,
                linestyle_opts=LineStyleOpts(...),
            ),
            opts.MarkLineItem(
                name="水平线",
                y_axis=50,
                linestyle_opts=LineStyleOpts(
                    type_="dashed",
                    color="#ff0000",
                ),
            ),
        ],
        symbol=["none", "none"],
        symbol_size=None,
        precision=2,
        label_opts=LabelOpts(...),
        linestyle_opts=LineStyleOpts(...),
    )
)
```

### 4.7 标记区域配置项 (MarkAreaOpts)

```python
bar.add_yaxis(
    "系列名",
    [1, 2, 3],
    markarea_opts=opts.MarkAreaOpts(
        is_silent=False,
        data=[
            (
                opts.MarkAreaItem(name="区域1", x="2024-01-01"),
                opts.MarkAreaItem(x="2024-01-07"),
            ),
            (
                opts.MarkAreaItem(name="区域2", x="2024-01-10", itemstyle_opts=opts.ItemStyleOpts(color="rgba(255,0,0,0.1)")),
                opts.MarkAreaItem(x="2024-01-15"),
            ),
        ],
        label_opts=LabelOpts(...),
        itemstyle_opts=ItemStyleOpts(...),
    )
)
```

---

## 5. 文字样式配置项 (TextStyleOpts)

```python
opts.TextStyleOpts(
    color=None,                 # 颜色
    font_style=None,            # 风格: "normal" / "italic" / "oblique"
    font_weight=None,           # 粗细: "normal" / "bold" / "bolder" / "lighter"
    font_family=None,          # 字体: "serif" / "sans-serif" / "monospace"
    font_size=None,             # 字号
    align=None,                 # 水平对齐
    vertical_align=None,        # 垂直对齐
    line_height=None,           # 行高
    background_color=None,      # 背景色
    border_color=None,          # 边框色
    border_width=None,         # 边框宽度
    border_radius=None,         # 圆角
    padding=None,               # 内边距
    shadow_color=None,          # 阴影色
    shadow_blur=None,           # 阴影模糊
    width=None,                 # 宽度
    height=None,                # 高度
    rich=None,                  # 富文本配置
)
```

---

## 6. 动画配置项 (AnimationOpts)

### 6.1 全局动画配置

```python
from pyecharts import options as opts

chart = Bar(init_opts=opts.InitOpts(
    animation_opts=opts.AnimationOpts(
        animation=True,               # 开启动画
        animation_threshold=2000,     # 动画阈值
        animation_duration=1000,       # 动画时长
        animation_easing="cubicOut",  # 缓动函数
        animation_delay=0,             # 动画延迟
        animation_duration_update=300, # 数据更新动画时长
        animation_easing_update="cubicOut",
        animation_delay_update=0,
    )
))
```

### 6.2 缓动函数 (animation_easing)

| 函数名 | 描述 |
|--------|------|
| `"linear"` | 线性 |
| `"quinticOut"` | 五次多项式缓出 |
| `"quarticOut"` | 四次多项式缓出 |
| `"cubicOut"` | 三次多项式缓出 (默认) |
| `"sinusoidalOut"` | 正弦缓出 |
| `"exponentialOut"` | 指数缓出 |
| `"quadraticOut"` | 二次多项式缓出 |
| `"cubicIn"` | 三次多项式缓入 |
| `"elasticIn"` | 弹性缓入 |
| `"backIn"` | 回退缓入 |

---

## 7. 特殊图表数据格式

### 7.1 K线图 (Candlestick)

```python
candlestick.add_yaxis(
    "K线",
    [
        [open, close, low, high],   # 单根K线
        [100, 102, 99, 101],
        [101, 103, 100, 102],
    ]
)
# 数据格式: List[List[float]] - [开盘, 收盘, 最低, 最高]
```

### 7.2 箱线图 (Boxplot)

```python
boxplot.add_yaxis(
    "箱线图",
    [
        [min, Q1, median, Q3, max],  # 单个箱线
        [12, 25, 50, 75, 98],
    ]
)
# 数据格式: List[List[float]] - [最小值, Q1, 中位数, Q3, 最大值]
```

### 7.3 热力图 (Heatmap)

```python
heatmap.add_yaxis(
    "热力图",
    [
        [x_index, y_index, value],  # 单个数据点
        [0, 0, 5],
        [0, 1, 10],
    ]
)
# 数据格式: List[List[number]] - [x索引, y索引, 数值]
```

### 7.4 关系图 (Graph)

```python
graph.add(
    "关系图",
    nodes=[
        opts.GraphNode(
            name="节点1",
            x=None, y=None,
            is_fixed=False,
            value="数值",
            category=0,
            symbol="circle",      # "circle" / "rect" / "triangle" / "diamond"
            symbol_size=10,
            itemstyle_opts=ItemStyleOpts(...),
            label_opts=LabelOpts(...),
        ),
    ],
    links=[
        opts.GraphLink(
            source="节点1",
            target="节点2",
            value="关系值",
            symbol=["none", "arrow"],
            symbol_size=10,
            linestyle_opts=LineStyleOpts(...),
        ),
    ],
    categories=[
        opts.GraphCategory(name="分类1"),
        opts.GraphCategory(name="分类2"),
    ],
    is_draggable=True,
    layout="force",              # "force" / "circular"
    roam=True,                   # 开启缩放
)
```

### 7.5 旭日图 (Sunburst)

```python
sunburst.add(
    "旭日图",
    data=[
        opts.SunburstItem(
            name="一级",
            children=[
                opts.SunburstItem(
                    name="二级",
                    value=10,
                    children=[...],
                    itemstyle_opts=ItemStyleOpts(...),
                    label_opts=LabelOpts(...),
                ),
            ],
        ),
    ],
    radius=[0, "90%"],
    label_opts=LabelOpts(...),
)
```

---

## 8. 各图表类型特有参数对比

### 8.1 图表分类与数据输入方式

PyEcharts 图表按数据输入方式分为两大类：

| 数据输入方式 | 图表类型 | 说明 |
|-------------|----------|------|
| **笛卡尔坐标系** | Bar, Line, Candlestick, Scatter, Boxplot, HeatMap, PictorialBar | 使用 `add_xaxis()` + `add_yaxis()` |
| **直接数据型** | Pie, Map, Geo, Graph, TreeMap, Sunburst, Funnel, Gauge, Radar, Liquid | 使用 `add()` 直接传入数据 |

### 8.2 各大类图表参数对比

#### 笛卡尔坐标系类 (Bar, Line, Candlestick, Scatter)

| 参数 | Bar | Line | Candlestick | Scatter | 说明 |
|------|-----|------|-------------|---------|------|
| **数据输入** | add_xaxis + add_yaxis | add_xaxis + add_yaxis | add_xaxis + add_yaxis | add_xaxis + add_yaxis | |
| **y_axis** | ✅ | ✅ | ✅ | ✅ | 数值数据 |
| **xaxis_data** | ✅ | ✅ | ✅ | ✅ | X轴类目数据 |
| **共同参数** | 15个 | 15个 | 15个 | 15个 | 见 8.3 |
| stack | ✅ | ✅ | ❌ | ❌ | 堆叠 |
| is_smooth | ❌ | ✅ | ❌ | ❌ | 平滑曲线 |
| is_step | ❌ | ✅ | ❌ | ❌ | 阶梯图 |
| symbol | ❌ | ✅ | ❌ | ✅ | 标记形状 |
| symbol_size | ❌ | ✅ | ❌ | ✅ | 标记大小 |
| bar_width | ✅ | ❌ | ✅ | ❌ | 柱宽 |
| areastyle_opts | ❌ | ✅ | ❌ | ❌ | 区域填充 |
| is_clip | ❌ | ✅ | ✅ | ❌ | 裁剪 |

#### 直接数据类 (Pie)

| 参数 | Pie | 说明 |
|------|-----|------|
| **数据输入** | add + data_pair | |
| **data_pair** | ✅ | (名称, 数值) 元组列表 |
| **共同参数** | 38个 | 见 8.4 |
| center | ✅ | 圆心位置 |
| radius | ✅ | 半径 |
| rosetype | ✅ | 玫瑰图类型 |
| label_opts | ✅ | 标签配置 |
| selected_mode | ✅ | 选中模式 |
| start_angle | ✅ | 起始角度 |

---

### 8.3 add_yaxis 共同参数 (笛卡尔坐标系类 15个)

以下参数在 Bar, Line, Candlestick, Scatter 中完全通用：

```python
# 数据相关
series_name="系列名",           # 系列名称
y_axis=[1, 2, 3],             # 数值数据

# 坐标系统
coordinate_system=None,        # 坐标系类型
coordinate_system_usage=None,
coord=None,                   # 坐标
xaxis_index=None,             # X轴索引
yaxis_index=None,             # Y轴索引

# 样式配置
color_by="series",            # 颜色方案

# 标记配置 (通用)
label_opts=LabelOpts(),       # 标签
itemstyle_opts=ItemStyleOpts(), # 图元样式
markpoint_opts=MarkPointOpts(), # 标记点
markline_opts=MarkLineOpts(),   # 标记线
markarea_opts=MarkAreaOpts(),   # 标记区域

# 交互配置
tooltip_opts=TooltipOpts(),   # 提示框
emphasis_opts=EmphasisOpts(), # 强调样式

# 数据编码
encode=None,                  # 数据编码
```

### 8.4 add 共同参数 (直接数据类 38个)

```python
# 数据
series_name="系列名",
data_pair=[("A", 100), ("B", 200)],  # (名称, 数值)

# 布局
center=["50%", "50%"],
radius=["0%", "75%"],
rosetype=None,               # 玫瑰图类型

# 标签
label_opts=LabelOpts(),
label_line_opts=LabelLineOpts(),

# 样式
color=None,
itemstyle_opts=ItemStyleOpts(),
empty_circle_style_opts=ItemStyleOpts(),

# 标记
markpoint_opts=MarkPointOpts(),
markline_opts=MarkLineOpts(),
markarea_opts=MarkAreaOpts(),

# 交互
tooltip_opts=TooltipOpts(),
emphasis_opts=EmphasisOpts(),
selected_mode="single",

# 其他
is_legend_hover_link=True,
is_clockwise=True,
is_avoid_label_overlap=True,
start_angle=90,
end_angle=360,
min_angle=0,
percent_precision=2,
is_still_show_zero_sum=True,
```

### 8.5 数据格式规范

| 图表类型 | 数据格式 | 示例 |
|----------|----------|------|
| **Bar/Line** | `List[number]` | `[1, 2, 3, 4, 5]` |
| **Pie/Funnel/Gauge** | `List[(str, number)]` | `[("A", 100), ("B", 200)]` |
| **Candlestick/Kline** | `List[[open, close, low, high]]` | `[[100, 102, 99, 101]]` |
| **Boxplot** | `List[[min, Q1, median, Q3, max]]` | `[[10, 25, 50, 75, 90]]` |
| **HeatMap** | `List[[x, y, value]]` | `[[0, 0, 5], [1, 0, 10]]` |
| **Scatter** | `List[number]` (X轴数值) | `[[1, 2], [3, 4]]` |
| **Graph** | `nodes + links` | `nodes=[], links=[]` |

### 8.2 柱状图 (Bar) 特有参数

```python
bar.add_yaxis(
    "系列名",
    [1, 2, 3],
    # 布局参数
    stack="总量",              # 堆叠名称
    bar_width="30%",           # 柱宽
    bar_min_height=0,          # 最小柱高
    category_gap="20%",        # 类目间距
    gap="30%",                 # 系列间距
    # 样式参数
    is_show_background=True,   # 显示背景
    background_style=opts.BarBackgroundStyleOpts(...),
    # 性能参数
    is_large=False,            # 大数据优化
    large_threshold=400,       # 大数据阈值
    # 特效参数
    is_round_cap=True,         # 圆角柱顶
    color_by="series",         # 颜色方案: "series" / "data"
)
```

### 8.3 折线图 (Line) 特有参数

```python
line.add_yaxis(
    "系列名",
    [1, 2, 3],
    # 线条样式
    is_smooth=True,            # 平滑曲线
    is_step=False,             # 阶梯图: "start" / "middle" / "end"
    # 标记点
    is_symbol_show=True,       # 显示标记点
    symbol="circle",           # 标记形状
    symbol_size=4,             # 标记大小
    # 数据处理
    is_connect_nones=True,     # 连接空值
    stack="总量",              # 堆叠
    sampling="lttb",           # 采样方式
    # 区域填充
    areastyle_opts=opts.AreaStyleOpts(opacity=0.3),
    # 末端标签
    end_label_opts=opts.LabelOpts(is_show=True),
)
```

### 8.4 饼图 (Pie) 特有参数

```python
pie.add(
    "系列名",
    data_pair=[
        ("A", 100),
        ("B", 200),
        ("C", 300),
    ],
    # 布局
    center=["50%", "50%"],     # 圆心位置
    radius=["0%", "75%"],      # 半径 [内, 外]
    rosetype="radius",         # 玫瑰图类型: "radius" / "area"
    # 标签
    label_opts=opts.LabelOpts(
        position="outside",    # outside/inside/center
        formatter="{b}: {d}%",
    ),
    # 样式
    itemstyle_opts=opts.ItemStyleOpts(border_radius=10),
    # 选中效果
    selected_mode="single",    # single/multiple
    selected_offset=20,         # 选中偏移
)
```

### 8.5 K线图/蜡烛图 (Candlestick/Kline) 特有参数

```python
candlestick.add_yaxis(
    "K线",
    [
        [open, close, low, high],
        [100, 102, 99, 101],   # [开盘, 收盘, 最低, 最高]
    ],
    bar_width="60%",           # K线宽度
    bar_max_width=None,         # 最大宽度
    layout=None,                # 布局
)
```

### 8.6 散点图 (Scatter) 特有参数

```python
scatter.add_yaxis(
    "散点",
    [1, 2, 3],
    # 标记参数
    symbol="circle",           # 标记形状: circle/rect/triangle/diamond
    symbol_size=10,             # 标记大小
    symbol_rotate=0,            # 标记旋转
    # 坐标系统
    coordinate_system="cartesian2d",  # cartesian2d/geo/polar
)
```

### 8.7 涟漪散点图 (EffectScatter) 特有参数

```python
effect_scatter.add_yaxis(
    "涟漪",
    [1, 2, 3],
    # 特效参数
    show_effect_on="render",    # render/emphasis
    ripple_num=3,               # 波纹数量
    ripple_scale=2.5,           # 波纹缩放
    period=4,                   # 动画周期
    symbol="circle",
    symbol_size=10,
)
```

### 8.8 热力图 (HeatMap) 特有参数

```python
heatmap.add_yaxis(
    "热力图",
    value=[
        [x_index, y_index, value],  # x索引, y索引, 数值
        [0, 0, 5],
        [0, 1, 10],
    ],
    point_size=20,              # 点大小
    min_opacity=0,             # 最小透明度
    max_opacity=1,              # 最大透明度
    blur_size=20,               # 模糊大小
)
```

### 8.9 箱线图 (Boxplot) 特有参数

```python
boxplot.add_yaxis(
    "箱线图",
    [
        [min, Q1, median, Q3, max],
        [12, 25, 50, 75, 98],  # 最小值, Q1, 中位数, Q3, 最大值
    ],
    chart_type="boxplot",       # boxplot/kde
    box_width=[7, 50],         # 箱宽范围
)
```

### 8.10 漏斗图 (Funnel) 特有参数

```python
funnel.add(
    "漏斗图",
    data_pair=[
        ("访问", 100),
        ("下载", 80),
        ("下单", 60),
        ("成交", 40),
    ],
    sort_="descending",        # 排序: descending/ascending/none
    gap=2,                     # 间隙
    label_opts=opts.LabelOpts(position="inside"),
)
```

### 8.11 仪表盘 (Gauge) 特有参数

```python
gauge.add(
    "仪表盘",
    data_pair=[
        ("完成率", 75),
    ],
    min_=0,                    # 最小值
    max_=100,                  # 最大值
    split_number=10,           # 分割段数
    axisline_opts=opts.AxisLineOpts(
        linestyle_opts=opts.LineStyleOpts(
            color=[
                [0.3, "#67e0e3"],
                [0.7, "#37a2da"],
                [1, "#fd666d"],
            ]
        )
    ),
    pointer_opts=opts.PointerOpts(length="75%"),
    detail_opts=opts.LabelOpts(formatter="{value}%"),
)
```

### 8.12 关系图 (Graph) 特有参数

```python
graph.add(
    "关系图",
    nodes=[
        {"name": "节点1", "category": 0, "symbol_size": 50},
        {"name": "节点2", "category": 1, "symbol_size": 30},
    ],
    links=[
        {"source": "节点1", "target": "节点2", "value": "关系"},
    ],
    categories=[
        {"name": "分类1"},
        {"name": "分类2"},
    ],
    # 布局参数
    layout="force",            # force/circular
    is_draggable=True,         # 可拖拽
    roam=True,                 # 可缩放
    # 样式参数
    edge_symbol=["none", "arrow"],
    edge_symbol_size=10,
    linestyle_opts=opts.LineStyleOpts(curveness=0.3),
    label_opts=opts.LabelOpts(),
)
```

### 8.13 象形柱状图 (PictorialBar) 特有参数

```python
pictorial_bar.add_yaxis(
    "象形柱",
    [10, 20, 30],
    # 图形参数
    symbol="path://M0,0 L20,0 L20,20 L0,20 Z",  # SVG 路径
    symbol_size=30,             # 图形大小
    symbol_pos="start",         # 位置: start/center/end
    symbol_offset=[0, 0],       # 偏移
    symbol_rotate="auto",       # 旋转
    symbol_repeat="original",   # 重复: original/fixed/none
    symbol_repeat_direction="start",  # 重复方向
    symbol_margin=10,           # 边距
    is_symbol_clip=True,        # 图形裁剪
)
```

### 8.14 地理坐标系 (Geo) 特有参数

```python
geo.add(
    "地图",
    data_pair=[("北京", 100), ("上海", 80)],
    # 地理参数
    maptype="china",           # 地图类型
    is_roam=True,              # 允许缩放
    center=[105, 36],          # 中心点
    zoom=1,                    # 缩放比例
    # 样式参数
    symbol="circle",
    symbol_size=10,
    point_size=5,              # 点大小
    blur_size=5,               # 模糊大小
    # 标签
    label_opts=opts.LabelOpts(is_show=False),
    linestyle_opts=opts.LineStyleOpts(color="#333"),
)
```

### 8.15 雷达图 (Radar) 特有参数

```python
radar.add(
    "雷达图",
    data=[
        {
            "name": "预算",
            "value": [80, 90, 70, 85, 90],
        },
    ],
    # 雷达参数
    radar_dim=["销售", "利润", "资产", "满意度", "市场"],
    radar_index=None,
    # 标记
    symbol="circle",
    symbol_size=4,
    # 区域填充
    area_opts=opts.AreaStyleOpts(opacity=0.3),
)
```

### 8.16 液体图 (Liquid) 特有参数

```python
liquid.add(
    "液体图",
    data=[0.6],                # 0-1 之间的数值
    # 形状
    shape="circle",            # circle/diamond/rect/triangle/pin/diamond
    # 动画
    is_animation=True,         # 开启动画
    animation_duration=1000,   # 动画时长
    animation_easing="cousicOut",
    # 轮廓
    is_outline_show=True,      # 显示轮廓
    outline_border_distance=10, # 轮廓距离
    outline_item_distance=10,  # 文字距离
    # 颜色
    color=["#1890ff"],        # 液体颜色
    background_color="#fff",   # 背景色
)
```

### 8.17 自定义图 (Custom) 特有参数

```python
custom.add(
    "自定义图",
    render_item=JsCode("""function(params, api) {
        // 自定义渲染逻辑
        return {
            type: 'rect',
            shape: {...},
            style: api.style()
        };
    }"""),
    data=[[12, 24, data], ...],
    coordinate_system="cartesian2d",
)
```

---

## 9. Grid 多图布局

```python
from pyecharts.charts import Bar, Line, Grid

# 创建子图表
bar = (
    Bar()
    .add_xaxis(["A", "B", "C"])
    .add_yaxis("柱状图", [1, 2, 3])
)

line = (
    Line()
    .add_xaxis(["A", "B", "C"])
    .add_yaxis("折线", [1, 2, 3])
)

# 创建 Grid 容器
grid = Grid(init_opts=opts.InitOpts(
    width="100%",
    height="800px"
))

# 添加子图表并设置位置
grid.add(
    bar,
    grid_opts=opts.GridOpts(
        pos_top="5%",
        pos_height="40%",
    )
)

grid.add(
    line,
    grid_opts=opts.GridOpts(
        pos_top="50%",
        pos_bottom="5%",
    )
)
```

---

## 10. 常用图表类型导入

```python
from pyecharts.charts import (
    Bar,                # 柱状图
    Line,               # 折线图
    Pie,                # 饼图
    Scatter,            # 散点图
    EffectScatter,      # 涟漪散点图
    Candlestick,        # K线图
    Boxplot,            # 箱线图
    HeatMap,            # 热力图
    Map,                # 地图
    Geo,                # 地理坐标系
    Graph,              # 关系图
    TreeMap,            # 树图
    Sunburst,           # 旭日图
    Parallel,           # 平行坐标系
    Radar,              # 雷达图
    Gauge,              # 仪表盘
    Funnel,             # 漏斗图
    PictorialBar,       # 象形柱状图
    ThemeRiver,         # 主题河流图
    Calendar,           # 日历图
    Liquid,             # 液体图
    Custom,             # 自定义图
    Grid,               # 网格布局
    Page,               # 页面布局
    Timeline,           # 时间线
)
```

---

## 11. 输出方法与类型

### 11.1 输出方法汇总

| 方法 | 返回类型 | 输出内容 | 典型用途 |
|------|----------|----------|----------|
| `dump_options()` | `str` | echarts 配置 JSON | API 接口返回、跨语言调用 |
| `dump_options_with_quotes()` | `str` | 带引号 JSON 字符串 | JS 变量赋值 |
| `render_embed()` | `str` | 完整 HTML 字符串 | 嵌入到现有页面 |
| `render(path)` | `str` | 文件路径 | 生成静态 HTML 文件 |
| `load_javascript()` | `Javascript` 对象 | echarts 库加载代码 | Jupyter notebook |

### 11.2 各输出方法详解

#### 11.2.1 dump_options() - 纯配置 JSON

```python
# 获取 echarts 配置对象 (不含容器信息)
options_json = chart.dump_options()

# 返回示例:
# {
#     "animation": true,
#     "series": [{"type": "bar", "data": [1,2,3]}],
#     "xAxis": {...},
#     "yAxis": {...}
# }

# 用途: API 接口返回、前后端分离
```

**特点:**
- ✅ 不包含容器尺寸、主题、渲染器
- ✅ 纯 echarts 配置，可用于任何 echarts 环境
- ✅ JSON 格式，便于解析和传输

#### 11.2.2 dump_options_with_quotes() - 带引号 JSON

```python
# 获取带引号的 JSON (用于 JS 变量赋值)
options_str = chart.dump_options_with_quotes()

# 返回: '{ "series": [...], ... }'  (外层带引号)
# 用途: 直接赋值给 JS 变量
```

**特点:**
- ✅ 外层带引号，可直接作为 JS 字符串使用
- ✅ 适用于前后端分离的手动拼接

#### 11.2.3 render_embed() - 嵌入 HTML

```python
# 获取完整 HTML 字符串
html = chart.render_embed()

# 返回结构:
# <!DOCTYPE html>
# <html>
# <head>
#     <script src="https://assets.pyecharts.org/assets/v6/echarts.min.js"></script>
# </head>
# <body>
#     <div id="xxx" class="chart-container" style="width:900px; height:500px;"></div>
#     <script>
#         var chart_xxx = echarts.init(...);
#         var option_xxx = {...};
#         chart_xxx.setOption(option_xxx);
#     </script>
# </body>
# </html>
```

**特点:**
- ✅ 包含容器 div (含尺寸)
- ✅ 包含 echarts.init() 初始化代码
- ✅ 包含 chart.setOption() 配置
- ✅ 可直接嵌入任意 HTML 页面

#### 11.2.4 render() - 生成 HTML 文件

```python
# 渲染到文件
file_path = chart.render("bar_chart.html")

# 参数:
# - path: 文件保存路径 (默认 "render.html")
# - template_name: 模板名称 (默认 "simple_chart.html")

# 返回: 保存的文件路径
```

**特点:**
- ✅ 生成完整的 HTML 文件
- ✅ 可指定保存路径
- ✅ 支持自定义模板

#### 11.2.5 render_notebook() - Jupyter 显示

```python
# 在 Jupyter Notebook 中渲染
chart.render_notebook()

# 返回: IPython.display.HTML 对象
# 特点: 只能在 Jupyter 环境中使用
```

### 11.3 输出内容对比

```
┌─────────────────────────────────────────────────────────────────┐
│                     render_embed() 输出结构                      │
├─────────────────────────────────────────────────────────────────┤
│  <!DOCTYPE html>                                                │
│  <html>                                                         │
│  <head>                                                         │
│      <script src="echarts.min.js"></script>    ← echarts 库    │
│  </head>                                                        │
│  <body>                                                         │
│      <div id="xxx" style="width:900px; height:500px"> ← 容器   │
│                                                                  │
│      <script>                                                   │
│          var chart_xxx = echarts.init(...)     ← 初始化         │
│          var option_xxx = {...}               ← 配置 (同 dump) │
│          chart_xxx.setOption(option_xxx)       ← 渲染           │
│      </script>                                                  │
│  </body>                                                        │
│  </html>                                                        │
└─────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                     dump_options() 输出结构                      │
├─────────────────────────────────────────────────────────────────┤
│  {                                                              │
│      "animation": true,                      ← 动画            │
│      "series": [...],                          ← 数据系列       │
│      "legend": {...},                          ← 图例           │
│      "tooltip": {...},                         ← 提示框         │
│      "xAxis": {...},                          ← X轴            │
│      "yAxis": {...},                          ← Y轴            │
│      "grid": {...},                           ← 网格           │
│      ...                                                           │
│  }                                                              │
└─────────────────────────────────────────────────────────────────┘
```

### 11.4 容器信息获取

```python
# 容器尺寸 (InitOpts 中设置)
chart = Bar(init_opts=opts.InitOpts(width="900px", height="500px"))
chart.width    # -> "900px"
chart.height   # -> "500px"
chart.theme    # -> "white"

# 渲染器类型
chart.renderer  # -> "canvas" 或 "svg"

# 图表 ID
chart.chart_id  # -> 自动生成的 UUID
```

### 11.5 使用场景推荐

| 场景 | 推荐方法 |
|------|----------|
| **API 接口返回** | `dump_options()` → 返回纯配置 |
| **嵌入已有页面** | `render_embed()` → 返回 HTML 片段 |
| **生成静态文件** | `render("chart.html")` → 保存 HTML 文件 |
| **Jupyter Notebook** | `render_notebook()` → 直接显示 |
| **手动拼接 JS** | `dump_options_with_quotes()` → 带引号 JSON |

---

## 12. 版本信息

- **PyEcharts 版本**: 2.1.0
- **文档基于**: pyecharts 源码分析
- **生成时间**: 2026-03-05
