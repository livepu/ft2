import pymysql
import threading
import re,time
from dbutils.pooled_db import PooledDB
from pymysql.cursors import DictCursor
from functools import wraps

class LaDb(object):
    # 移除类属性_pool和_pid
    def __init__(self, dbconfig=None):
        self._load_config(dbconfig)
        self._pool = None  # 改为实例属性，直至多实例下的不同dbconfig。同时一个实例下的线程安全。
        self._pool_lock = threading.Lock()  # 实例级连接池锁
        self._init_pool()
        self._local = threading.local() # 线程局部状态存储
        # 实例级缓存
        self._metadata_cache = {
            'constraints': {},  # 表约束缓存 {table_name: constraints}
            'structure': {},     # 表结构缓存 {table_name: columns}
            'query': {}          # 新增查询结果缓存 {sql: (result, timestamp)}
            }
        self._cache_ttl = 3600  # 默认缓存过期时间(秒)
        
    def _load_config(self, dbconfig):
        """加载数据库配置"""
        if dbconfig is None:
            from . import conf__g
            dbconfig = conf__g.Config.mysql
        self.dbconfig = dbconfig

    def _init_pool(self):
        """实例级连接池初始化"""
        if self._pool is None or self._pool._closed:
            with self._pool_lock:
                if self._pool is None or self._pool._closed:  # 双重检查
                    self._pool = PooledDB(
                        creator=pymysql,
                        maxconnections=10,  # 单个实例连接数减少
                        ping=2,#更智能的ping检测
                        blocking=True,
                        host=self.dbconfig['host'],
                        port=self.dbconfig['port'],
                        user=self.dbconfig['username'],
                        passwd=self.dbconfig['password'],
                        db=self.dbconfig['dbname'],
                        charset=self.dbconfig['charset'],
                        cursorclass=DictCursor
                    )

    def close(self):
        """安全关闭连接池"""
        with self._pool_lock:
            if self._pool:
                self._pool.close()
                self._pool = None

    def __del__(self):
        """析构时自动关闭"""
        self.close()
    @property
    def _state(self):
        """获取当前线程的查询状态（带线程内锁）"""
        if not hasattr(self._local, 'state'):
            self._local.state = {
                'table': '',
                'where_keys': '',
                'where_vals': [],
                'fields': '*',
                'limit': '',
                'order_by': '',
                'group_by': '',
                'showsql': False, #True/False 或数字级别 (1=基础/2=详细)
                '_lock': threading.RLock()  # 新增线程内锁
            }
        return self._local.state

    # 修改 _clear 方法（保持原有逻辑但使用状态字典）
    def _clear(self):
        """重置当前线程的查询状态"""
        self._state.update({
            'table': '',
            'where_keys': '',
            'where_vals': [],
            'fields': '*',
            'limit': '',
            'order_by': '',
            'group_by': '',
            # 注意：不重置 _lock 属性
        })

    @staticmethod
    def is_query(sql):
        """判断是否为查询操作（排除SELECT INTO）"""
        sql = sql.strip().lower()
        # 先检查是否是SELECT INTO
        if re.search(r'^select\b.*?\binto\b', sql, re.IGNORECASE):
            return False
        # 常规查询判断
        query_keywords = r'^(select|with|show|desc|describe|explain|call)\b'
        return re.search(query_keywords, sql, re.IGNORECASE) is not None
    @staticmethod
    def needs_commit(sql):
        """判断是否为写操作（包含SELECT INTO）"""
        sql = sql.strip().lower()
        # 先检查是否是SELECT INTO
        if re.search(r'^select\b.*?\binto\b', sql, re.IGNORECASE):
            return True
        # 常规写操作判断
        write_keywords = r'^(insert|update|delete|replace|merge)\b'
        return re.search(write_keywords, sql, re.IGNORECASE) is not None

    def query(self, sql=None, tuple_values=None):
        if not sql:
            raise Exception('sql语句不能为空')
        if tuple_values and not isinstance(tuple_values, (tuple, list)):
            raise Exception('参数类型必须是元组或列表')
        
        if not self.is_query(sql):
            raise PermissionError("query()方法仅允许查询操作(SELECT/WITH/SHOW/DESC/EXPLAIN/CALL)")
        
        return self._execute(sql, tuple_values, fetch="all")

    def _execute(self, sql, params=None, fetch=None):
        """执行SQL的核心方法（增加重试机制）"""
        max_retries = 3
        base_delay = 1  # 初始延迟1秒

        for attempt in range(max_retries):
            try:
                # 修改这里：从 self._pool 而不是 LaDb._pool 获取连接
                with self._pool.connection() as conn:
                    # 新增连接活性检查
                    conn.ping(reconnect=True)
                    try:
                        with conn.cursor() as cursor:
                            if self._state['showsql']:
                                print("Executing:", cursor.mogrify(sql, params))
                            cursor.execute(sql, params)
                            result = self._process_result(cursor, fetch, sql)   
                            # 非查询操作立即提交
                            if self.needs_commit(sql):
                                conn.commit()
                            return result
                    except pymysql.Error as e:
                        print(f"事务操作错误: {e}")
                        conn.rollback()  # 移动到 with 块内部
                        raise
            except (pymysql.OperationalError, pymysql.InterfaceError) as e:
                if attempt < max_retries - 1:  # 前两次尝试重试
                    delay = base_delay * (2 ** attempt)  # 指数退避
                    print(f"数据库连接异常 ({e}), {delay}秒后重试...")
                    time.sleep(delay)
                    continue
                raise

            except Exception as e:
                print(f"未知错误: {e}")
                raise

    def _process_result(self, cursor, fetch, sql):
        """结果处理抽离为独立方法"""
        if fetch is None and self.is_query(sql):
            fetch = "all"
            
        if fetch == "all":
            return cursor.fetchall()
        elif fetch == "one":
            return cursor.fetchone()
        elif fetch == "value":
            row = cursor.fetchone()
            return row[0] if row else None
        else :
            return cursor.rowcount if cursor.rowcount >=0 else cursor.lastrowid
        

    def table(self, name):
        """设置表名（线程安全）"""
        with self._state['_lock']:
            self._state['table'] = self.dbconfig['pre'] + name if self.dbconfig['pre'] else name
        return self


    # 定义比较符号常量（按类型分组）
    COMPARE_SIGNS = [
        # 基础比较
        '=', '<>', '!=', '>', '<', '>=', '<=', 
        # 模糊匹配
        'like', 'not like', 
        # 集合操作
        'in', 'not in', 
        # NULL判断
        'is', 'is not', 
        # 范围判断
        'between', 'not between',
    ]

    @staticmethod
    def _build_where_conditions(where, where_keys='', where_vals=[]):
        '''要实现一个where({a:[判断符号,参数,逻辑符],b:[判断符号,参数,逻辑符],c:[判断符号,参数,逻辑符]}) 可以实现a or b and c'''
        """优化条件拼接方法，支持所有SQL操作符"""
        conditions = []
        condition_operators = []  # 存储每个条件之间的逻辑运算符
        for key, item in where.items():
            # 默认逻辑运算符为 AND
            cond_operator = 'and'
            if isinstance(item, (list, tuple)) and len(item) >= 2:
                # 如果条件中有第三个参数，则使用指定的逻辑运算符
                if len(item) >= 3:
                    cond_operator = item[2].lower() if item[2].lower() in ('and', 'or') else 'and'
                # 处理复杂条件 [操作符, 值, 逻辑符?]
                sign = item[0] if item[0] in LaDb.COMPARE_SIGNS else '='
                
                # 特殊处理 in/not in 操作符
                if sign in ['in', 'not in']:
                    if not isinstance(item[1], (list, tuple)):
                        raise ValueError(f"{sign} 操作符的值必须是列表或元组")
                    placeholders = ','.join(['%s'] * len(item[1]))
                    conditions.append(f"{key} {sign} ({placeholders})")
                    where_vals.extend(item[1])
                # 特殊处理 is/is not 操作符
                elif sign in ['is', 'is not']:
                    if item[1] is None or str(item[1]).lower() == 'null':
                        conditions.append(f"{key} {sign} NULL")
                    else:
                        raise ValueError(f"{sign} 操作符的值必须是 None 或 'null'")
                # 特殊处理 between/not between 操作符
                elif sign in ['between', 'not between']:
                    if not isinstance(item[1], (list, tuple)) or len(item[1]) != 2:
                        raise ValueError(f"{sign} 操作符的值必须是包含两个值的列表或元组")
                    conditions.append(f"{key} {sign} %s AND %s")
                    where_vals.extend(item[1])
                else:
                    # 处理其他操作符
                    sign_str = f' {sign} ' if sign in ['like', 'not like'] else sign
                    conditions.append(f"{key}{sign_str}%s")
                    where_vals.append(item[1])
            else:
                # 简单条件
                conditions.append(f"{key}=%s")
                where_vals.append(item)
            condition_operators.append(cond_operator)
            
        # 第一个条件
        where_keys = conditions[0]
        # 从第二个条件开始拼接
        for i in range(1, len(conditions)):
            where_keys += f" {condition_operators[i]} {conditions[i]}"
            
        return {'keys': where_keys, 'vals': tuple(where_vals)}

    #适度丰富就可以了，不要过度复杂，不然直接原生sql。
    # 查询条件，这里需要一个巧妙的算法，where(a).where(b or c)=> a and (b or c),把每个where独立一个完整的()
    def where(self, where=None, value=None, method='and',wrap=None):
        #wrap in [(,(),)]
        """线程安全的条件设置"""
        with self._state['_lock']:  # 加锁保护
            if value is not None:
                where = {where: value}
            # 判断参数
            if where is not None:
                if not isinstance(where, dict):
                    raise Exception('查询条件必须是字典类型')
                where_keys, where_vals = '', [] 
                # 查询字段 ，原函数保留了可以作为独立拼接多次where_keys,where_vals的功能
                _select = self._build_where_conditions(where, where_keys, where_vals)
                where_keys = _select['keys'] 
                where_vals = _select['vals']

                # 直接处理括号逻辑
                if wrap == '(':
                    where_keys = f"({where_keys}"
                elif wrap == ')':
                    where_keys = f"{where_keys})"
                elif wrap == '()': #针对多参数的情况，把where_keys用()包裹
                    where_keys = f"({where_keys})"
            # 更新状态
            if self._state.get('where_keys'):  # 检查 _state['where_keys'] 是否存在

                self._state['where_keys'] += f' {method} {where_keys}'
                self._state['where_vals'] += where_vals
            else:
                self._state['where_keys'] = where_keys
                self._state['where_vals'] = where_vals
            #print(self)
        return self
    # 修改关键操作方法示例
    def fields(self, params=None):
        """线程安全的字段设置"""
        with self._state['_lock']:  # 加锁保护
            if not params:
                self._state['fields'] = '*'
            else:
                if isinstance(params, list):
                    params = ','.join(params)
                self._state['fields'] = params
        return self
    # 分页
    def page(self, page=1, rows=10):
        with self._state['_lock']:
            self._state['limit'] = f"{(page - 1) * rows},{rows}"
        return self

    # 构建limit函数
    def limit(self, a: int, b: int = None):
        with self._state['_lock']:
            self._state['limit'] = f"{a},{b}" if b else str(a)
        return self
    # 归组# 修改 groupBy 方法
    def groupBy(self, param=None):
        with self._state['_lock']:
            if param and isinstance(param, str):
                self._state['group_by'] = param
        return self


    # 修改 orderBy 方法
    def orderBy(self, order_by=None):
        with self._state['_lock']:
            if order_by:
                self._state['order_by'] = order_by
        return self


    # 修改 format_sql 方法（使用状态字典替代实例属性）
    def format_sql(self):
        sql = "SELECT {} FROM {}".format(self._state['fields'], self._state['table'])
        if self._state['where_keys']:
            sql += f" WHERE {self._state['where_keys']}"
        if self._state['group_by']:
            sql += f" GROUP BY {self._state['group_by']}"
        if self._state['order_by']:
            sql += f" ORDER BY {self._state['order_by']}"
        if self._state['limit']:
            sql += f" LIMIT {self._state['limit']}"
        return sql
    # 正确用法（无需类状态），用装饰器来适配需要clear()的方法
    @staticmethod
    def auto_clear(func):
        @wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                return func(self, *args, **kwargs)
            finally:
                self._clear()
        return wrapper


    @auto_clear  
    def get(self, use_cache=False, cache_ttl=None):
        """获取多条记录
        :param use_cache: 是否使用缓存
        :param cache_ttl: 缓存时间(秒)，None表示使用默认值
        """
        sql = self.format_sql()
        if not use_cache:
            return self._execute(
                sql=sql, 
                params=self._state['where_vals'],
                fetch="all"
            )
        
        # 生成缓存键
        cache_key = f"{sql}:{self._state['where_vals']}"
        
        # 检查缓存是否存在且未过期
        if cache_key in self._metadata_cache['query']:
            cached_time = self._metadata_cache['query'][cache_key][1]
            ttl = cache_ttl if cache_ttl is not None else self._cache_ttl
            if (time.time() - cached_time) < ttl:
                return self._metadata_cache['query'][cache_key][0]
        
        # 执行查询并缓存结果
        result = self._execute(
            sql=sql,
            params=self._state['where_vals'],
            fetch="all"
        )
        self._metadata_cache['query'][cache_key] = (result, time.time())
        return result

    @auto_clear
    def first(self):
        sql = self.format_sql()
        return self._execute(
            sql=sql,
            params=self._state['where_vals'],
            fetch="one"
        )
    # 同步修改 value 方法
    @auto_clear
    def value(self, field=None):
        if not field:
            raise Exception('查询字段不能为空')
        
        # 强制只查询指定字段
        self.fields(field)
        result = self.first()
        
        if not result or field not in result:
            raise Exception('没有查询到该字段或指定的查询结果为空')

        return result[field]
    ##增加一个updateOrInsert，如果存在，更新，不存在，插入。
    @auto_clear
    def updateOrInsert(self,where,data={}):  #这个函数，后续再考虑是否要改成那种where().updateOrInsert()。这里没必要改了，通过where()，再获取组合数据更麻烦
        with self._state['_lock']:
            if not data:
                raise Exception('更新数据不能为空')
            # 查询是否存在记录
            self.where(where).fields('*') #这里不直接first()或者get()，因为会清空状态。
            sql = self.format_sql()
            # 使用新的执行方法获取结果
            old_data = self._execute(
                sql=sql,
                params=self._state['where_vals'],
                fetch="one"
            )
            #参照insert()的返回结果，这里不存在批量操作
            result = {
                'inserted': 0,
                'updated': 0,
                'skipped': 0,
                'errors': 0,
                'error_details': [],
            }
            
            if not old_data:  # 无记录时插入
                if self._state['showsql']:
                    print('插入:', {**where, **data})
                insert_result = self.insert({**where, **data})
                result['inserted'] = insert_result['inserted']
                if insert_result['errors'] > 0:
                    result['errors'] = insert_result['errors']
                    result['error_details'] = insert_result['error_details']
            else:
                # 检查 data 的所有键是否都是 old_data 的子集，且数据一致
                if(set(data.keys()).issubset(old_data.keys()) 
                    and all(data[key] == old_data[key] for key in data)):
                    if self._state['showsql']:  
                        print('相同数据data,跳过更新')
                    result['skipped'] = 1
                else:
                    if self._state['showsql']:
                        print('不同data，更新')
                    update_result = self.update(data) #前面已经运行过where()了
                    result['updated'] = update_result if isinstance(update_result, int) else 1
            return result


    def _get_unique_constraints(self):
        """获取表的所有唯一约束（带实例级缓存）"""
        table_name = self._state['table']
        
        # 检查实例缓存
        if table_name in self._metadata_cache['constraints']:
            return self._metadata_cache['constraints'][table_name]

        """获取表的所有唯一约束（格式优化为字典）"""
        sql = f"""
        SELECT 
            tc.CONSTRAINT_TYPE,
            GROUP_CONCAT(kcu.COLUMN_NAME ORDER BY kcu.ORDINAL_POSITION) AS columns
        FROM 
            information_schema.TABLE_CONSTRAINTS tc
        JOIN 
            information_schema.KEY_COLUMN_USAGE kcu 
            ON tc.CONSTRAINT_NAME = kcu.CONSTRAINT_NAME 
            AND tc.TABLE_SCHEMA = kcu.TABLE_SCHEMA
            AND tc.TABLE_NAME = kcu.TABLE_NAME
        WHERE 
            tc.TABLE_SCHEMA = DATABASE()
            AND tc.TABLE_NAME = '{table_name}'
            AND tc.CONSTRAINT_TYPE IN ('PRIMARY KEY', 'UNIQUE')
        GROUP BY 
            tc.CONSTRAINT_NAME, tc.CONSTRAINT_TYPE;
        """
        showsql=self._state['showsql']
        if showsql<=1:
            self.showsql(0) #这里不需要输出测试信息。
        result = self._execute(sql, fetch="all")
        self.showsql(showsql)
        #print(result)
        # 新增结构转换逻辑
        constraints = {
            'primary': [],
            'unique': []
        }
        for row in result:
            key = 'primary' if row['CONSTRAINT_TYPE'] == 'PRIMARY KEY' else 'unique'
            columns = tuple(row['columns'].split(','))  # 转换为元组便于后续处理
            if columns not in constraints[key]:        # 去重
                constraints[key].append(columns)
        
        # 存入实例缓存
        self._metadata_cache['constraints'][table_name] = constraints
        return constraints
    #插入数据，支持批量。这个函数不涉及状态，直接使用。
    def insert(self, data, on_conflict='ignore'):
        """
        支持单条/批量插入及自动错误跳过的增强方法：
        
        :param data: 单条字典或批量列表（列表元素为字典）
        :param on_conflict: 插入时遇到重复键的处理策略 
            'ignore' - 忽略重复（默认）
            'update' - 覆盖更新现有记录，这个模式可以替代updateOrInsert
            其他值  - 普通插入（可能因重复键失败）
        """
        # 参数类型校验
        if not data:
            raise Exception('新增内容不能为空')
        if not isinstance(data, (dict, list)):
            raise TypeError("参数必须为字典或字典列表")
        
        # 统一处理数据格式
        if isinstance(data, list):
            if len(data) == 0:
                raise ValueError("数据列表不能为空")
            # 强制所有数据项的键完全一致
            keys = list(data[0].keys())
            for item in data:
                if list(item.keys()) != keys:
                    raise ValueError("批量操作要求所有数据项字段完全一致")
            data_list = data
        else:
            keys = list(data.keys())
            data_list = [data]
            
        # 构造SQL语句
        placeholders = ', '.join(['%s'] * len(keys))
        # 新增字段转义逻辑
        escaped_keys = [f"`{k}`" for k in keys]  # 统一转义所有字段名

        # 只有update或ignore模式才需要检查约束
        if on_conflict in ('update', 'ignore'): #需要判断重复的模式，最好的情况是有唯一键。主键适合获取id后更新
            # 新增约束检查逻辑
            constraints = self._get_unique_constraints()
            required_cols = None
            #print(constraints)
            # 优先检查唯一约束
            if constraints['unique']:
                for unique_set in constraints['unique']:
                    if all(col in keys for col in unique_set):  # 检查是否包含该唯一键的所有字段
                        required_cols = unique_set
                        break
            # 没有匹配的唯一约束时检查主键
            if not required_cols and constraints['primary']:
                primary_set = constraints['primary'][0]
                if all(col in keys for col in primary_set):  # 检查是否包含主键的所有字段
                    required_cols = primary_set
            # 最终校验
            if not required_cols:
                err_msg = []
                if constraints['unique']:
                    err_msg.append(f"必须包含至少一个唯一键字段组: {constraints['unique']}")
                if constraints['primary']:
                    err_msg.append(f"或主键字段: {constraints['primary'][0]}")
                raise Exception(f"更新验证失败: {'; '.join(err_msg)}, 当前字段: {keys}")
            
        if on_conflict == 'update':
            update_fields = [f"`{k}` = VALUES({k})" for k in keys]
            sql = f"""
            INSERT INTO `{self._state['table']}` ({', '.join(escaped_keys)})
            VALUES ({placeholders})
            ON DUPLICATE KEY UPDATE {', '.join(update_fields)}
            """
        elif on_conflict == 'ignore':
            sql = f"""
            INSERT IGNORE INTO `{self._state['table']}` ({', '.join(escaped_keys)})
            VALUES ({placeholders})
            """
        else:
            sql = f"""
            INSERT INTO `{self._state['table']}` ({', '.join(escaped_keys)})
            VALUES ({placeholders})
            """
            
        # 优化点3：增强VALUES参数容错处理
        params_list = [tuple(item.get(k) for k in keys) for item in data_list]  # 使用get避免KeyError
        
        result = {
            'inserted': 0, 
            'updated': 0, 
            'skipped': 0, 
            'errors': 0,
            'error_details': [],
            'batch_success': False
        }
        try:
            # 优先尝试批量操作
            try:
                # 使用连接池上下文管理
                with self._pool.connection() as conn:
                    with conn.cursor() as cs:
                        count_sql = f"SELECT COUNT(*) AS num FROM {self._state['table']}" #仅用于这个地方计数的，放到with里面。
                        # 使用当前连接的游标获取初始行数
                        cs.execute(count_sql) #注意这里不能用自定义的_execute()，连接冲突的。
                        startnum = cs.fetchone()['num']
                        if self._state['showsql']:
                            # 显示批量SQL模板
                            print(f"批量执行 SQL: {cs.mogrify(sql, params_list[0])}")

                        cs.executemany(sql, params_list)
                        conn.commit()
                        row_count = cs.rowcount

                        # 使用当前连接的游标获取最终行数
                        cs.execute(count_sql)
                        endnum = cs.fetchone()['num']
                        # 标记批量成功并计算结果
                        total = len(params_list)
                        #print(row_count)
                        result['batch_success'] = True

                        # 精确插入数 = 表行数差值（依赖事务隔离级别）
                        inserted = endnum - startnum
                        # 冲突数 = 总操作数 - 插入数
                        conflict_count = total - inserted
                        # 更新数 = (ROW_COUNT - 插入数) // 2（因每次更新贡献 ROW_COUNT=2）
                        updated = (row_count - inserted) // 2
                        # 忽略数 = 冲突数 - 更新数（字段未变化的冲突）
                        skipped = conflict_count - updated
                        result['inserted'] = inserted
                        result['updated'] = updated
                        result['skipped'] = skipped


            #批量处理失败，进入逐条更新模式
            except pymysql.Error as e:
                print(f"批量执行失败({e})，开始逐条处理...")

                # 逐条处理时使用连接池上下文
                with self._pool.connection() as conn:
                    #conn.autocommit(False)
                    #这个属性错误，pymysql和dbutils默认是关闭的。

                    with conn.cursor() as cs:
                        for idx, params in enumerate(params_list):
                            try:
                                # 保持连接活性
                                conn.ping(reconnect=True)
                                
                                if self._state['showsql']:
                                    print(f"执行 SQL: {cs.mogrify(sql, params)}")
                                
                                cs.execute(sql, params)
                                
                                # 精确结果判断
                                if cs.rowcount == 1:  # 插入操作
                                    result['inserted'] += 1
                                elif cs.rowcount == 2:  # 更新操作
                                    result['updated'] += 1
                                else:  # 无变化或忽略
                                    result['skipped'] += 1
                                        
                                conn.commit()
                            except pymysql.IntegrityError as e:
                                # 使用当前连接进行回滚
                                conn.rollback()
                                if e.args[0] == 1062:
                                    result['skipped'] += 1
                                else:
                                    result['errors'] += 1
                                    result['error_details'].append({
                                        'index': idx,
                                        'params': params,
                                        'error': str(e)
                                    })
                                raise e
                            except Exception as e:
                                conn.rollback()
                                result['errors'] += 1
                                result['error_details'].append({
                                    'index': idx,
                                    'params': params,
                                    'error': str(e)
                                })
                                raise e
                    #with cs结束

        except Exception as e:
            print(e)
            raise e
        return result
    # 更新内容
    @auto_clear
    def update(self, data=None):
         # 条件判断
        if not data:
            raise Exception('更新内容不能为空')
        if not isinstance(data, dict):
            raise Exception('参数必须是字典类型')
        if not self._state['where_keys'] or not self._state['where_vals']:
            raise Exception('必须先调用where()方法设置查询条件')
        # 更新字段
        set_keys = ','.join([f"{key}=%s" for key in data.keys()])
        set_vals = list(data.values())
        # 合并dict并转化为元组
        val_list = tuple(set_vals + list(self._state['where_vals']))
    
        sql = f"UPDATE {self._state['table']} SET {set_keys} WHERE {self._state['where_keys']}"
        if self._state['showsql']:
            print(f"执行 SQL: {sql}")
            print(f"参数: {val_list}")
        
        return self._execute(sql, val_list)
            
    # 删除数据（根据where_keys和where_vals是否为空判断）
    @auto_clear
    def delete(self):
        if not self._state['table']:
            raise ValueError("在执行DELETE操作前，必须先调用table()方法设置表名")
        # 参数校验移至 try 块内
        if not self._state['where_keys'] or not self._state['where_vals']:
            raise ValueError("在执行DELETE操作前，必须先调用where()方法设置WHERE条件")

        sql = f"DELETE FROM {self._state['table']} WHERE {self._state['where_keys']}"
        return self._execute(sql, self._state['where_vals'])

    #启动错误sql错误提示。
    def showsql(self, showsql=True):
        with self._state['_lock']:  # 虽然技术上不需要，但保持风格统一
            self._state['showsql'] = showsql
        return self
    
    #实例级缓存清理
    def clear_metadata_cache(self, table_name=None):
        """清理实例级元数据缓存"""
        if table_name:
            self._metadata_cache['constraints'].pop(table_name, None)
            self._metadata_cache['structure'].pop(table_name, None)
        else:
            self._metadata_cache['constraints'].clear()
            self._metadata_cache['structure'].clear()
        return self