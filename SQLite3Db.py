import sqlite3
import re
from dataclasses import dataclass, field
from enum import Enum
from functools import wraps
from typing import Any, Dict, List, Optional, Tuple, Union
from pathlib import Path


class FetchType(Enum):
    ALL = 'all'
    ONE = 'one'
    VALUE = 'value'


class ResultType(Enum):
    DICT = 'dict'
    TUPLE = 'tuple'


@dataclass
class QueryState:
    table: str = ''
    where_keys: str = ''
    where_vals: List[Any] = field(default_factory=list)
    fields: str = '*'
    limit: str = ''
    order_by: str = ''
    group_by: str = ''
    joins: List[str] = field(default_factory=list)
    debug_level: int = 0


class SQLite3Db:
    """
    SQLite3 同步数据库操作类 - 专为缓存设计
    
    特性：
    - 简洁的链式查询接口
    - 自动提交模式（适合缓存）
    - 支持内存数据库（:memory:）
    - SQLite3特有的PRAGMA优化
    """
    
    COMPARE_SIGNS = [
        '=', '<>', '!=', '>', '<', '>=', '<=',
        'like', 'not like',
        'in', 'not in',
        'is', 'is not',
        'between', 'not between',
    ]

    def __init__(self, db_path: Union[str, Path] = None, **options):
        """
        初始化 SQLite3 数据库连接
        
        :param db_path: 数据库文件路径，None表示内存数据库
        :param options: 配置选项
            - journal_mode: DELETE/TRUNCATE/PERSIST/MEMORY/WAL/OFF (默认WAL)
            - synchronous: OFF/NORMAL/FULL (默认NORMAL)
            - cache_size: 缓存页数 (默认-64000，约64MB)
            - temp_store: DEFAULT/FILE/MEMORY (默认MEMORY)
        """
        if db_path is None:
            self.db_path = ":memory:"
        else:
            self.db_path = str(db_path)
            Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        self._connection: Optional[sqlite3.Connection] = None
        self._state = QueryState()
        self._options = {
            'journal_mode': 'WAL',
            'synchronous': 'NORMAL',
            'cache_size': -64000,
            'temp_store': 'MEMORY',
            **options
        }
        
        self._connect()
        self._apply_pragmas()

    def _connect(self):
        """建立数据库连接"""
        self._connection = sqlite3.connect(
            self.db_path,
            check_same_thread=False,
            isolation_level=None  # 自动提交模式
        )
        # 启用外键支持
        self._connection.execute("PRAGMA foreign_keys = ON")
        # 设置行工厂为字典模式
        self._connection.row_factory = sqlite3.Row

    def _apply_pragmas(self):
        """应用SQLite3优化PRAGMA"""
        pragmas = [
            f"PRAGMA journal_mode = {self._options['journal_mode']}",
            f"PRAGMA synchronous = {self._options['synchronous']}",
            f"PRAGMA cache_size = {self._options['cache_size']}",
            f"PRAGMA temp_store = {self._options['temp_store']}",
            "PRAGMA mmap_size = 268435456",  # 256MB内存映射
        ]
        for pragma in pragmas:
            try:
                self._connection.execute(pragma)
            except sqlite3.Error:
                pass  # 某些PRAGMA可能不支持

    def close(self):
        """关闭数据库连接"""
        if self._connection:
            self._connection.close()
            self._connection = None

    def __del__(self):
        """析构时自动关闭连接"""
        self.close()

    def __enter__(self):
        """上下文管理器入口"""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """上下文管理器出口"""
        self.close()

    def _clear_state(self):
        """重置查询状态"""
        self._state = QueryState()

    @staticmethod
    def is_query(sql: str) -> bool:
        """判断是否为查询操作"""
        sql = sql.strip().lower()
        return re.search(r'^(select|with|pragma|explain)\b', sql, re.IGNORECASE) is not None

    def _build_where_conditions(self, where: Dict[str, Any]) -> Tuple[str, Tuple[Any, ...]]:
        """构建 WHERE 条件"""
        conditions = []
        operators = []
        values = []

        for key, item in where.items():
            cond_operator = 'and'
            is_function_call = '(' in key and ')' in key

            if isinstance(item, (list, tuple)) and len(item) >= 2:
                if len(item) >= 3:
                    cond_operator = item[2].lower() if item[2].lower() in ('and', 'or') else 'and'

                sign = item[0] if item[0] in self.COMPARE_SIGNS else '='

                if sign in ['in', 'not in']:
                    if not isinstance(item[1], (list, tuple)):
                        raise ValueError(f"{sign} 操作符的值必须是列表或元组")
                    placeholders = ','.join(['?'] * len(item[1]))
                    field_name = key if is_function_call else f'"{key}"'
                    conditions.append(f'{field_name} {sign} ({placeholders})')
                    values.extend(item[1])
                elif sign in ['is', 'is not']:
                    if item[1] is None or str(item[1]).lower() == 'null':
                        field_name = key if is_function_call else f'"{key}"'
                        conditions.append(f'{field_name} {sign} NULL')
                    else:
                        raise ValueError(f"{sign} 操作符的值必须是 None 或 'null'")
                elif sign in ['between', 'not between']:
                    if not isinstance(item[1], (list, tuple)) or len(item[1]) != 2:
                        raise ValueError(f"{sign} 操作符的值必须是包含两个值的列表或元组")
                    field_name = key if is_function_call else f'"{key}"'
                    conditions.append(f'{field_name} {sign} ? AND ?')
                    values.extend(item[1])
                else:
                    sign_str = f' {sign} ' if sign in ['like', 'not like'] else sign
                    field_name = key if is_function_call else f'"{key}"'
                    conditions.append(f'{field_name}{sign_str}?')
                    values.append(item[1])
            else:
                field_name = key if is_function_call else f'"{key}"'
                conditions.append(f'{field_name}=?')
                values.append(item)

            operators.append(cond_operator)

        if not conditions:
            return '', ()

        where_keys = conditions[0]
        for i in range(1, len(conditions)):
            where_keys += f" {operators[i]} {conditions[i]}"

        return where_keys, tuple(values)

    def _build_select_sql(self, state: QueryState) -> str:
        """构建 SELECT SQL"""
        sql = f'SELECT {state.fields} FROM "{state.table}"'

        if state.joins:
            sql += ' ' + ' '.join(state.joins)

        if state.where_keys:
            sql += f" WHERE {state.where_keys}"

        if state.group_by:
            sql += f" GROUP BY {state.group_by}"

        if state.order_by:
            sql += f" ORDER BY {state.order_by}"

        if state.limit:
            parts = state.limit.split(',')
            if len(parts) == 2:
                offset, limit = parts
                sql += f" LIMIT {limit} OFFSET {offset}"
            else:
                sql += f" LIMIT {state.limit}"

        return sql

    def _process_result(self, cursor: sqlite3.Cursor, fetch: FetchType, r_type: ResultType) -> Any:
        """处理查询结果"""
        if fetch == FetchType.ALL:
            rows = cursor.fetchall()
            if r_type == ResultType.DICT:
                return [dict(row) for row in rows]
            return rows
        elif fetch == FetchType.ONE:
            row = cursor.fetchone()
            if row is None:
                return None
            if r_type == ResultType.DICT:
                return dict(row)
            return row
        elif fetch == FetchType.VALUE:
            row = cursor.fetchone()
            if row is None:
                return None
            return row[0]
        else:
            return cursor.rowcount

    def _execute(
        self,
        sql: str,
        params: Optional[Tuple[Any, ...]] = None,
        fetch: Optional[FetchType] = None,
        r_type: ResultType = ResultType.DICT
    ) -> Any:
        """执行 SQL 的核心方法"""
        if self._connection is None:
            raise Exception("数据库连接已关闭")

        if self._state.debug_level:
            print(f"执行 SQL: {sql}")
            if params:
                print(f"参数: {params}")

        try:
            cursor = self._connection.execute(sql, params or ())

            if fetch is None and self.is_query(sql):
                fetch = FetchType.ALL

            if fetch:
                return self._process_result(cursor, fetch, r_type)
            else:
                return cursor.rowcount

        except sqlite3.Error as e:
            raise Exception(f"SQL 执行错误: {e}")

    @staticmethod
    def auto_clear(func):
        """自动清理状态的装饰器"""
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            finally:
                self._clear_state()
        return wrapper

    # ==================== 查询接口 ====================

    def query(
        self,
        sql: str,
        tuple_values: Optional[Tuple[Any, ...]] = None,
        r_type: ResultType = ResultType.DICT
    ) -> Any:
        """
        执行原始 SQL 查询
        
        :param sql: SQL 语句
        :param tuple_values: 参数元组
        :param r_type: 返回类型
        :return: 查询结果
        """
        if not sql:
            raise Exception('SQL 语句不能为空')

        if not self.is_query(sql):
            raise PermissionError("query() 方法仅允许查询操作")

        return self._execute(sql, tuple_values, FetchType.ALL, r_type)

    def table(self, name: str) -> 'SQLite3Db':
        """设置表名"""
        self._state.table = name
        return self

    def where(
        self,
        where: Optional[Union[Dict[str, Any], str]] = None,
        value: Optional[Any] = None,
        method: str = 'and',
        wrap: Optional[str] = None
    ) -> 'SQLite3Db':
        """设置 WHERE 条件"""
        if value is not None:
            where = {where: value}

        if where is not None:
            if not isinstance(where, dict):
                raise Exception('查询条件必须是字典类型')

            where_keys, where_vals = self._build_where_conditions(where)

            if wrap == '(':
                where_keys = f"({where_keys}"
            elif wrap == ')':
                where_keys = f"{where_keys})"
            elif wrap == '()':
                where_keys = f"({where_keys})"

            if self._state.where_keys:
                self._state.where_keys += f' {method} {where_keys}'
                self._state.where_vals += list(where_vals)
            else:
                self._state.where_keys = where_keys
                self._state.where_vals = list(where_vals)

        return self

    def fields(self, params: Optional[Union[str, List[str]]] = None) -> 'SQLite3Db':
        """设置查询字段"""
        if not params:
            self._state.fields = '*'
        elif isinstance(params, list):
            self._state.fields = ','.join([f'"{field}"' for field in params])
        elif isinstance(params, str):
            # 简单处理，如果包含括号则不添加引号
            if '(' in params:
                self._state.fields = params
            else:
                fields = [f.strip() for f in params.split(',') if f.strip()]
                self._state.fields = ','.join([f'"{f}"' for f in fields])
        else:
            self._state.fields = params
        return self

    def limit(self, a: int, b: Optional[int] = None) -> 'SQLite3Db':
        """设置 LIMIT"""
        self._state.limit = f"{a},{b}" if b else str(a)
        return self

    def page(self, page: int = 1, rows: int = 10) -> 'SQLite3Db':
        """分页查询"""
        self._state.limit = f"{(page - 1) * rows},{rows}"
        return self

    def orderBy(self, order_by: str) -> 'SQLite3Db':
        """设置 ORDER BY"""
        self._state.order_by = order_by
        return self

    def groupBy(self, param: str) -> 'SQLite3Db':
        """设置 GROUP BY"""
        self._state.group_by = param
        return self

    def join(self, table: str, on: str, join_type: str = 'INNER') -> 'SQLite3Db':
        """JOIN 查询 - SQLite3不支持RIGHT JOIN"""
        join_type = join_type.upper()
        if join_type == 'RIGHT':
            raise NotImplementedError("SQLite3 不支持 RIGHT JOIN，请使用 LEFT JOIN 并交换表顺序")
        join_clause = f"{join_type} JOIN \"{table}\" ON {on}"
        self._state.joins.append(join_clause)
        return self

    def leftJoin(self, table: str, on: str) -> 'SQLite3Db':
        """LEFT JOIN"""
        return self.join(table, on, 'LEFT')

    def innerJoin(self, table: str, on: str) -> 'SQLite3Db':
        """INNER JOIN"""
        return self.join(table, on, 'INNER')

    def format_sql(self) -> str:
        """格式化 SQL"""
        return self._build_select_sql(self._state)

    @auto_clear
    def get(self, r_type: ResultType = ResultType.DICT) -> Any:
        """获取多条记录"""
        sql = self._build_select_sql(self._state)
        params = tuple(self._state.where_vals)
        return self._execute(sql, params, FetchType.ALL, r_type)

    @auto_clear
    def first(self, r_type: ResultType = ResultType.DICT) -> Any:
        """获取第一条记录"""
        original_limit = self._state.limit
        self._state.limit = '0,1'
        try:
            sql = self._build_select_sql(self._state)
            params = tuple(self._state.where_vals)
            return self._execute(sql, params, FetchType.ONE, r_type)
        finally:
            self._state.limit = original_limit

    @auto_clear
    def value(self, field: str) -> Any:
        """获取单个字段的值"""
        if not field:
            raise Exception('查询字段不能为空')
        self.fields(field)
        result = self.first(ResultType.TUPLE)
        return result[0] if result else None

    # ==================== 写操作接口 ====================

    def insert(self, data: Union[Dict[str, Any], List[Dict[str, Any]]],
               on_conflict: str = None) -> Dict[str, Any]:
        """
        插入数据

        :param data: 单条字典或批量列表
        :param on_conflict: 冲突处理策略
            - None: 默认INSERT，冲突时报错
            - 'replace': INSERT OR REPLACE，冲突时删除旧行插入新行
            - 'ignore': INSERT OR IGNORE，冲突时跳过不报错
        :return: 操作结果统计
        """
        if not data:
            raise Exception('插入数据不能为空')
        if not isinstance(data, (dict, list)):
            raise TypeError("参数必须为字典或字典列表")

        if isinstance(data, list):
            if len(data) == 0:
                raise ValueError("数据列表不能为空")
            keys = list(data[0].keys())
            for item in data:
                if list(item.keys()) != keys:
                    raise ValueError("批量操作要求所有数据项字段完全一致")
            data_list = data
        else:
            keys = list(data.keys())
            data_list = [data]

        placeholders = ', '.join(['?'] * len(keys))
        escaped_keys = [f'"{k}"' for k in keys]

        # 构建INSERT语句
        if on_conflict == 'replace':
            insert_type = 'INSERT OR REPLACE'
        elif on_conflict == 'ignore':
            insert_type = 'INSERT OR IGNORE'
        elif on_conflict is None:
            insert_type = 'INSERT'
        else:
            raise ValueError("on_conflict参数必须是 None, 'replace' 或 'ignore'")

        sql = f'{insert_type} INTO "{self._state.table}" ({', '.join(escaped_keys)}) VALUES ({placeholders})'

        result = {
            'inserted': 0,
            'errors': 0,
            'error_details': []
        }

        try:
            for item in data_list:
                params = tuple(item.get(k) for k in keys)
                self._execute(sql, params)
                result['inserted'] += 1
        except Exception as e:
            result['errors'] += 1
            result['error_details'].append({'error': str(e)})

        self._clear_state()
        return result

    @auto_clear
    def update(self, data: Dict[str, Any]) -> int:
        """
        更新数据
        
        :param data: 要更新的字段字典
        :return: 影响的行数
        """
        if not data:
            raise Exception('更新内容不能为空')
        if not isinstance(data, dict):
            raise Exception('参数必须是字典类型')
        if not self._state.where_keys or not self._state.where_vals:
            raise Exception('必须先调用 where() 方法设置查询条件')

        set_keys = ','.join([f'"{key}"=?' for key in data.keys()])
        set_vals = list(data.values())
        val_list = tuple(set_vals + self._state.where_vals)

        sql = f'UPDATE "{self._state.table}" SET {set_keys} WHERE {self._state.where_keys}'
        
        if self._state.debug_level:
            print(f"执行 SQL: {sql}")
            print(f"参数: {val_list}")

        return self._execute(sql, val_list)

    @auto_clear
    def delete(self) -> int:
        """
        删除数据
        
        :return: 影响的行数
        """
        if not self._state.table:
            raise ValueError("在执行 DELETE 操作前，必须先调用 table() 方法设置表名")
        if not self._state.where_keys or not self._state.where_vals:
            raise ValueError("在执行 DELETE 操作前，必须先调用 where() 方法设置 WHERE 条件")

        sql = f'DELETE FROM "{self._state.table}" WHERE {self._state.where_keys}'
        params = tuple(self._state.where_vals)
        return self._execute(sql, params)

    # ==================== 数据库管理接口 ====================

    def create_database(self, db_path: Union[str, Path]) -> 'SQLite3Db':
        """
        创建新数据库（SQLite3 中就是创建新文件）
        
        :param db_path: 新数据库文件路径
        :return: 新的 SQLite3Db 实例
        """
        return SQLite3Db(db_path)

    def create_table(self, table_name: str, columns: Dict[str, str], 
                     primary_key: Optional[str] = None,
                     if_not_exists: bool = True) -> bool:
        """
        创建表
        
        :param table_name: 表名
        :param columns: 字段定义，如 {'id': 'INTEGER', 'name': 'TEXT NOT NULL'}
        :param primary_key: 主键字段名
        :param if_not_exists: 如果表不存在才创建
        :return: 是否成功
        """
        if_not_exists_sql = "IF NOT EXISTS " if if_not_exists else ""
        
        column_defs = []
        for col_name, col_type in columns.items():
            if primary_key and col_name == primary_key:
                column_defs.append(f'"{col_name}" {col_type} PRIMARY KEY')
            else:
                column_defs.append(f'"{col_name}" {col_type}')
        
        sql = f"CREATE TABLE {if_not_exists_sql}\"{table_name}\" ({', '.join(column_defs)})"
        
        try:
            self._execute(sql)
            return True
        except Exception as e:
            print(f"创建表失败: {e}")
            return False

    def create_index(self, index_name: str, table_name: str, 
                     columns: List[str], unique: bool = False) -> bool:
        """
        创建索引 - 缓存查询性能优化
        
        :param index_name: 索引名
        :param table_name: 表名
        :param columns: 字段列表
        :param unique: 是否唯一索引
        :return: 是否成功
        """
        unique_sql = "UNIQUE " if unique else ""
        columns_sql = ', '.join([f'"{col}"' for col in columns])
        sql = f"CREATE {unique_sql}INDEX IF NOT EXISTS \"{index_name}\" ON \"{table_name}\" ({columns_sql})"
        
        try:
            self._execute(sql)
            return True
        except Exception as e:
            print(f"创建索引失败: {e}")
            return False

    def drop_table(self, table_name: str, if_exists: bool = True) -> bool:
        """
        删除表
        
        :param table_name: 表名
        :param if_exists: 只有表存在时才删除
        :return: 是否成功
        """
        if_exists_sql = "IF EXISTS " if if_exists else ""
        sql = f"DROP TABLE {if_exists_sql}\"{table_name}\""
        
        try:
            self._execute(sql)
            return True
        except Exception as e:
            print(f"删除表失败: {e}")
            return False

    def table_exists(self, table_name: str) -> bool:
        """
        检查表是否存在
        
        :param table_name: 表名
        :return: 是否存在
        """
        sql = "SELECT name FROM sqlite_master WHERE type='table' AND name=?"
        result = self._execute(sql, (table_name,), FetchType.ONE, ResultType.DICT)
        return result is not None

    def get_tables(self) -> List[str]:
        """
        获取所有表名
        
        :return: 表名列表
        """
        sql = "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        results = self._execute(sql, None, FetchType.ALL, ResultType.DICT)
        return [row['name'] for row in results]

    def get_table_info(self, table_name: str) -> List[Dict[str, Any]]:
        """
        获取表结构信息
        
        :param table_name: 表名
        :return: 字段信息列表
        """
        sql = f'PRAGMA table_info("{table_name}")'
        return self._execute(sql, None, FetchType.ALL, ResultType.DICT)

    def get_index_info(self, table_name: str) -> List[Dict[str, Any]]:
        """
        获取表索引信息
        
        :param table_name: 表名
        :return: 索引信息列表
        """
        sql = f'PRAGMA index_list("{table_name}")'
        return self._execute(sql, None, FetchType.ALL, ResultType.DICT)

    def vacuum(self) -> bool:
        """
        压缩数据库 - 释放未使用的空间
        
        :return: 是否成功
        """
        try:
            self._execute("VACUUM")
            return True
        except Exception as e:
            print(f"VACUUM 失败: {e}")
            return False

    def debug_level(self, level: int = 1) -> 'SQLite3Db':
        """设置调试级别，显示执行的SQL语句"""
        self._state.debug_level = level
        return self

    def optimize(self) -> bool:
        """
        优化数据库 - 分析表并更新统计信息
        
        :return: 是否成功
        """
        try:
            self._execute("PRAGMA optimize")
            return True
        except Exception as e:
            print(f"优化失败: {e}")
            return False
