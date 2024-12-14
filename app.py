from flask import Flask, render_template, request, flash, redirect, url_for
from flask import jsonify

import pymssql
import logging

app = Flask(__name__)

# 连接数据库
def get_db_connection():
    conn = pymssql.connect(
        server='DESKTOP-M05GEV8',
        user='sa',
        password='123456',
        database='Task_1'
    )
    return conn

# 获取游标
connection = get_db_connection()
cursor = connection.cursor()

@app.route('/admin_dashboard')
def admin_dashboard():
    return render_template('admin_dashboard.html')  # 管理员首页（控制面板）

@app.route('/register', methods=['GET', 'POST'])
def register_page():
    error_message = None
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            error_message = "两次密码输入不一致"
        else:
            conn = get_db_connection()
            cursor = conn.cursor()

            # 检查用户名是否已存在
            cursor.execute("SELECT * FROM users WHERE username = %s", (username,))
            existing_user = cursor.fetchone()
            if existing_user:
                error_message = "用户名已存在，请选择其他用户名"
            else:
                # 插入新用户记录
                cursor.execute("INSERT INTO users (username, password) VALUES (%s, %s)", (username, password))
                conn.commit()
                conn.close()
                return redirect(url_for('login_page'))  # 注册成功后跳转到登录页面

            conn.close()

    return render_template('register_page.html', error_message=error_message)


@app.route('/', methods=['GET', 'POST'])
def login_page():
    error_message = None  # 用于存储错误信息
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # 连接数据库，检查用户名和密码
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = %s AND password = %s", (username, password))
        user = cursor.fetchone()

        if user:
            return redirect(url_for('user_page'))  # 用户认证成功，跳转到用户页面
        else:
            cursor.execute("SELECT * FROM admin WHERE username = %s AND password = %s", (username, password))
            admin = cursor.fetchone()

            if admin:
                return redirect(url_for('admin_dashboard'))  # 管理员认证成功，跳转到管理员控制面板
            else:
                error_message = "用户名或密码错误！"  # 如果认证失败，设置错误信息

    return render_template('login_page.html', error_message=error_message)  # 渲染登录页面并传递错误信息


@app.route('/user_page')
def user_page():
    conn = get_db_connection()
    cursor = conn.cursor(as_dict=True)

    # 查询学院、一级学科、二级学科和导师信息
    query = """
    SELECT 
    c.college_code,  -- 确保这行正确地查询了学院代码
    c.college_name, 
    c.total_admission AS college_total_admission, 
    c.recommendation_admission AS college_recommendation_admission,
    fs.subject_code AS first_subject_code,  -- 一级学科代码
    fs.subject_name AS first_subject_name, 
    fs.total_admission AS first_total_admission, 
    fs.recommendation_admission AS first_recommendation_admission,
    fs.description AS first_subject_description,
    ss.subject_code AS second_subject_code,  -- 二级学科代码
    ss.subject_name AS second_subject_name,
    ss.exam_subjects,
    m.mentor_name
FROM college c
LEFT JOIN first_subject fs ON c.id = fs.college_id
LEFT JOIN second_subject ss ON fs.id = ss.first_subject_id
LEFT JOIN mentor_second_subject mss ON ss.id = mss.second_subject_id
LEFT JOIN mentor m ON mss.mentor_id = m.mentor_id
ORDER BY c.college_name, fs.subject_name, ss.subject_name

    """

    cursor.execute(query)
    rows = cursor.fetchall()
    conn.close()

    # 处理成嵌套结构
    data = {}
    for row in rows:
        college_name = f"{row['college_code']} {row['college_name']}"
        if college_name not in data:
            data[college_name] = {
                'college_name': college_name,
                'total_admission': row['college_total_admission'],
                'recommendation_admission': row['college_recommendation_admission'],
                'first_subjects': {}
            }

        first_subject_name = f"{row['first_subject_code']} {row['first_subject_name']}"
        if first_subject_name not in data[college_name]['first_subjects']:
            data[college_name]['first_subjects'][first_subject_name] = {
                'subject_name': first_subject_name,
                'total_admission': row['first_total_admission'],
                'recommendation_admission': row['first_recommendation_admission'],
                'description': row['first_subject_description'],
                'second_subjects': {}
            }

        second_subject_name = f"{row['second_subject_code']} {row['second_subject_name']}"
        if second_subject_name not in data[college_name]['first_subjects'][first_subject_name]['second_subjects']:
            data[college_name]['first_subjects'][first_subject_name]['second_subjects'][second_subject_name] = {
                'subject_name': second_subject_name,
                'exam_subjects': row['exam_subjects'],
                'directors': []
            }

        if row['mentor_name']:
            data[college_name]['first_subjects'][first_subject_name]['second_subjects'][second_subject_name][
                'directors'].append({
                'name': row['mentor_name']
            })

    # 转换为列表格式供模板渲染
    formatted_data = [
        {
            'college_name': college_data['college_name'],
            'total_admission': college_data['total_admission'],
            'recommendation_admission': college_data['recommendation_admission'],
            'first_subjects': [
                {
                    'subject_name': fs_data['subject_name'],
                    'total_admission': fs_data['total_admission'],
                    'recommendation_admission': fs_data['recommendation_admission'],
                    'description': fs_data['description'],
                    'second_subjects': [
                        {
                            'subject_name': ss_data['subject_name'],
                            'exam_subjects': ss_data['exam_subjects'],
                            'directors': ss_data['directors']
                        }
                        for ss_data in fs_data['second_subjects'].values()
                    ]
                }
                for fs_data in college_data['first_subjects'].values()
            ]
        }
        for college_data in data.values()
    ]

    return render_template('user_page.html', data=formatted_data)


@app.route('/admin_page', methods=['GET', 'POST'])
def admin_page():
    conn = get_db_connection()
    cursor = conn.cursor(as_dict=True)

    if request.method == 'POST':
        data = request.form
        for key, value in data.items():
            if key.startswith('qualification_'):
                mentor_id = key.split('_')[1]
                has_admission_qualification = value
                cursor.execute("""
                    UPDATE mentor
                    SET has_admission_qualification = %s
                    WHERE mentor_id = %s
                """, (has_admission_qualification, mentor_id))
        conn.commit()

    cursor.execute("""
        SELECT 
            mentor_id, 
            mentor_name, 
            mentor_title, 
            mentor_description, 
            mentor_email, 
            mentor_phone, 
            has_admission_qualification 
        FROM mentor
        WHERE has_admission_qualification = '是'
    """)
    mentors = cursor.fetchall()
    conn.close()

    return render_template('admin_page.html', mentors=mentors)


@app.route('/update_mentor_qualification', methods=['POST'])
def update_mentor_qualification():
    conn = get_db_connection()
    cursor = conn.cursor()

    for key, value in request.form.items():
        if key.startswith('qualification_'):
            mentor_id = key.split('_')[1]
            cursor.execute("""
                UPDATE mentor 
                SET has_admission_qualification = %s 
                WHERE mentor_id = %s
            """, (value, mentor_id))

    conn.commit()
    conn.close()

    return redirect(url_for('admin_page'))


@app.route('/linxuan_page', methods=['GET'])
def linxuan_page():
    conn = get_db_connection()  # 连接数据库
    cursor = conn.cursor(as_dict=True)

    query = """
        SELECT mentor_id, mentor_name, mentor_title, mentor_description,
               mentor_email, mentor_phone, has_admission_qualification
        FROM mentor
        WHERE has_admission_qualification = '否'
    """

    cursor.execute(query)
    mentors = cursor.fetchall()

    conn.close()
    return render_template('linxuan_page.html', mentors=mentors)


@app.route('/update_mentor_selection', methods=['POST'])
def update_mentor_selection():
    conn = get_db_connection()
    cursor = conn.cursor()

    mentor_ids = request.form.getlist('mentor_ids')

    for mentor_id in mentor_ids:
        selected_title = request.form.get(f'mentor_{mentor_id}')
        if selected_title:
            # 更新导师的 mentor_title 和 has_admission_qualification
            cursor.execute("""
                UPDATE mentor
                SET mentor_title = %s, has_admission_qualification = '是'
                WHERE mentor_id = %s
            """, (selected_title, mentor_id))

    conn.commit()
    conn.close()

    return redirect('/linxuan_page')  # 刷新页面

# In app.py
@app.route('/subject_management')
def subject_management():
    return render_template('subject_management.html')

@app.route('/college_management')
def college_management():
    return render_template('college_management.html')

@app.route('/college_management_add', methods=['GET', 'POST'])
def college_management_add():
    if request.method == 'POST':
        college_name = request.form['college_name']
        college_code = request.form['college_code']
        total_admission = request.form['total_admission']
        recommendation_admission = request.form['recommendation_admission']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            INSERT INTO college (college_name, college_code, total_admission, recommendation_admission)
            VALUES (%s, %s, %s, %s)
        ''', (college_name, college_code, total_admission, recommendation_admission))
        conn.commit()
        conn.close()

        return redirect(url_for('college_management'))
    return render_template('college_management_add.html')


@app.route('/college_management_delete', methods=['GET', 'POST'])
def college_management_delete():
    if request.method == 'POST':
        college_name = request.form['college_name']

        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('''
            DELETE FROM second_subject WHERE first_subject_id IN 
            (SELECT id FROM first_subject WHERE college_id IN 
            (SELECT id FROM college WHERE college_name = %s))
        ''', (college_name,))

        cursor.execute('''
            DELETE FROM first_subject WHERE college_id IN 
            (SELECT id FROM college WHERE college_name = %s)
        ''', (college_name,))

        cursor.execute('DELETE FROM college WHERE college_name = %s', (college_name,))
        conn.commit()
        conn.close()

        return redirect(url_for('college_management'))
    return render_template('college_management_delete.html')

@app.route('/college_management_select', methods=['GET', 'POST'])
def college_management_select():
    conn = get_db_connection()
    cursor = conn.cursor(as_dict=True)

    # 当接收到表单提交的学院名称时
    if request.method == 'POST':
        college_name = request.form['college_name']

        # 查询学院及其下属学科信息
        query = """
        SELECT 
            c.college_code, 
            c.college_name, 
            c.total_admission AS college_total_admission, 
            c.recommendation_admission AS college_recommendation_admission,
            fs.subject_code AS first_subject_code, 
            fs.subject_name AS first_subject_name, 
            ss.subject_code AS second_subject_code,  
            ss.subject_name AS second_subject_name
        FROM college c
        LEFT JOIN first_subject fs ON c.id = fs.college_id
        LEFT JOIN second_subject ss ON fs.id = ss.first_subject_id
        WHERE c.college_name LIKE %s
        ORDER BY c.college_name, fs.subject_name, ss.subject_name
        """

        # 使用模糊查询查找学院名称
        cursor.execute(query, ('%' + college_name + '%',))
        rows = cursor.fetchall()
        conn.close()

        # 如果找到相关学院，处理为嵌套字典结构
        data = {}
        for row in rows:
            college_name = f"{row['college_code']} {row['college_name']}"
            if college_name not in data:
                data[college_name] = {
                    'college_name': college_name,
                    'total_admission': row['college_total_admission'],
                    'recommendation_admission': row['college_recommendation_admission'],
                    'first_subjects': {}
                }

            first_subject_name = f"{row['first_subject_code']} {row['first_subject_name']}"
            if first_subject_name not in data[college_name]['first_subjects']:
                data[college_name]['first_subjects'][first_subject_name] = {
                    'subject_name': first_subject_name,
                    'second_subjects': {}
                }

            second_subject_name = f"{row['second_subject_code']} {row['second_subject_name']}"
            if second_subject_name not in data[college_name]['first_subjects'][first_subject_name]['second_subjects']:
                data[college_name]['first_subjects'][first_subject_name]['second_subjects'][second_subject_name] = {
                    'subject_name': second_subject_name
                }

        # 转换为列表格式供模板渲染
        formatted_data = [
            {
                'college_name': college_data['college_name'],
                'total_admission': college_data['total_admission'],
                'recommendation_admission': college_data['recommendation_admission'],
                'first_subjects': [
                    {
                        'subject_name': fs_data['subject_name'],
                        'second_subjects': [
                            {
                                'subject_name': ss_data['subject_name']
                            }
                            for ss_data in fs_data['second_subjects'].values()
                        ]
                    }
                    for fs_data in college_data['first_subjects'].values()
                ]
            }
            for college_data in data.values()
        ]

        return render_template('college_management_select.html', data=formatted_data)

    # GET 请求时显示页面
    return render_template('college_management_select.html', data=None)

@app.route('/college_management_edit', methods=['GET', 'POST'])
def college_management_edit():
    conn = get_db_connection()
    cursor = conn.cursor(as_dict=True)

    if request.method == 'POST':
        # 获取表单提交的修改信息
        college_name = request.form.get('college_name')  # 获取学院名称（只读，不可修改）
        new_college_code = request.form.get('college_code')  # 修改后的学院编号
        new_total_admission = request.form.get('total_admission')  # 修改后的总招生数
        new_recommendation_admission = request.form.get('recommendation_admission')  # 修改后的推免数

        # 校验是否所有字段都填写了
        if not new_college_code or not new_total_admission or not new_recommendation_admission:
            flash("所有字段都必须填写！")
            return redirect(request.url)  # 如果有空字段，重新加载页面

        logging.info(
            f"Updating college: {college_name}, new code: {new_college_code}, new total_admission: {new_total_admission}, new recommendation_admission: {new_recommendation_admission}")

        # 更新学院信息的 SQL 查询
        update_query = """
        UPDATE college
        SET college_code = %s,
            total_admission = %s,
            recommendation_admission = %s
        WHERE college_name = %s
        """
        cursor.execute(update_query,
                       (new_college_code, new_total_admission, new_recommendation_admission, college_name))
        conn.commit()

        logging.info(f"Updated college info for: {college_name}")

        # 提示修改成功并重定向到学院管理页面
        flash('学院信息更新成功！')
        return redirect(url_for('college_management'))  # 重定向到学院管理页面

    elif request.method == 'GET':
        # 获取查询参数中的学院名称
        college_name = request.args.get('college_name', '').strip()

        if college_name:
            # 查询学院的原始信息，进行模糊查询
            query = """
            SELECT college_code, college_name, total_admission, recommendation_admission
            FROM college
            WHERE college_name LIKE %s
            """
            cursor.execute(query, ('%' + college_name + '%',))  # 使用 %like% 模糊查询
            row = cursor.fetchone()
            conn.close()

            if row:
                # 如果找到学院信息，将其传递到模板
                return render_template('college_management_edit.html', college=row)
            else:
                flash('未找到该学院，请检查输入！')
                return redirect(url_for('college_management_edit'))  # 如果未找到学院，重新加载页面
        else:
            return render_template('college_management_edit.html', college=None)

    return render_template('college_management_edit.html', college=None)


# 查询学院根据名称
# 查询学院根据名称
def query_college_by_name(college_name):
    if not college_name:  # 如果 college_name 为 None 或空字符串，返回 None
        return None
    query = "SELECT id, college_code, college_name, total_admission, recommendation_admission FROM college WHERE college_name LIKE %s"
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(query, ('%' + college_name + '%',))
    college = cursor.fetchone()
    conn.close()
    return college


# 插入一级学科
def insert_first_subject(college_id, subject_code, subject_name, description, subject_type, total_admission, recommendation_admission):
    query = """
    INSERT INTO first_subject (college_id, subject_code, subject_name, description, subject_type, total_admission, recommendation_admission)
    VALUES (%s, %s, %s, %s, %s, %s, %s)
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(query, (college_id, subject_code, subject_name, description, subject_type, total_admission, recommendation_admission))
    conn.commit()
    conn.close()

# 路由：一级学科管理页面
@app.route('/first_subject_management')
def first_subject_management():
    return render_template('first_subject_management.html')

# 路由：查询学院及其一级学科
@app.route('/search_college_and_first_subjects', methods=['POST'])
def search_college_and_first_subjects():
    college_name = request.form['college_name']
    college = query_college_by_name(college_name)

    if college is None:
        return jsonify({"success": False, "message": "未找到该学院"})

    college_id = college[0]
    query_first_subjects = "SELECT subject_code, subject_name FROM first_subject WHERE college_id = %s"
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(query_first_subjects, (college_id,))
    first_subjects = cursor.fetchall()

    first_subjects_list = [
        {'subject_code': fs[0], 'subject_name': fs[1]} for fs in first_subjects
    ]

    return jsonify({
        "success": True,
        "college": {
            "college_code": college[1],
            "college_name": college[2],
            "total_admission": college[3],
            "recommendation_admission": college[4]
        },
        "first_subjects": first_subjects_list
    })

def insert_first_subject(college_id, subject_code, subject_name, description, subject_type, total_admission, recommendation_admission):
    sql = """
    INSERT INTO first_subject (college_id, subject_code, subject_name, description, subject_type, total_admission, recommendation_admission)
    VALUES (?, ?, ?, ?, ?, ?, ?)
    """
    cursor.execute(sql, (college_id, subject_code, subject_name, description, subject_type, total_admission, recommendation_admission))
    connection.commit()


@app.route('/first_subject_management_add', methods=['GET', 'POST'])
def first_subject_management_add():
    if request.method == 'GET':
        # 直接渲染页面，处理前端表单的展示
        return render_template('first_subject_management_add.html')

    if request.method == 'POST':
        if request.is_json:
            data = request.get_json()
        else:
            data = request.form.to_dict()

        try:
            college_id = int(data.get('college_id', 0))
            total_admission = int(data.get('total_admission', 0))
            recommendation_admission = int(data.get('recommendation_admission', 0))
        except ValueError:
            return jsonify({"success": False, "message": "数值字段必须为整数"})

        # 验证 college_id 是否有效
        if college_id <= 0:
            return jsonify({"success": False, "message": "无效的学院 ID，请重新查询学院。"})

        subject_code = data.get('subject_code')
        subject_name = data.get('subject_name')
        description = data.get('description')
        subject_type = data.get('subject_type')

        # 验证字段是否完整
        if not all([college_id, subject_code, subject_name, description, subject_type, total_admission, recommendation_admission]):
            return jsonify({"success": False, "message": "所有字段都必须填写！"})

        if college_id <= 0:
            return jsonify({"success": False, "message": "无效的学院 ID，请重新查询学院后再试。"})

        try:
            insert_first_subject(
                college_id,
                subject_code,
                subject_name,
                description,
                subject_type,
                total_admission,
                recommendation_admission
            )
            return jsonify({"success": True, "message": "一级学科添加成功"})
        except Exception as e:
            return jsonify({"success": False, "message": str(e)})

@app.route('/first_subject_management_delete', methods=['GET', 'POST'])
def first_subject_management_delete():
    if request.method == 'POST':
        subject_id = request.form['subject_id']  # 从表单中获取学科 ID

        # 执行删除操作，删除对应一级学科以及它下的二级学科
        cursor = connection.cursor()
        cursor.execute('''
            DELETE FROM second_subject WHERE first_subject_id = %s
        ''', (subject_id,))
        cursor.execute('''
            DELETE FROM first_subject WHERE subject_id = %s
        ''', (subject_id,))
        connection.commit()

        return redirect(url_for('first_subject_management'))  # 重定向到一级学科管理界面

    # 渲染页面
    return render_template('first_subject_management_delete.html')


@app.route('/first_subject_management_select', methods=['GET', 'POST'])
def first_subject_management_select():
    if request.method == 'POST':
        subject_name = request.form['subject_name']  # 根据学科名称查询

        # 执行查询操作
        cursor = connection.cursor()
        cursor.execute('''
            SELECT * FROM first_subject WHERE subject_name LIKE %s
        ''', ('%' + subject_name + '%',))  # 模糊查询
        subjects = cursor.fetchall()

        # 将查询结果传递给模板
        return render_template('first_subject_management_select.html', subjects=subjects)

    # 渲染页面
    return render_template('first_subject_management_select.html')


@app.route('/first_subject_management_edit', methods=['GET', 'POST'])
def first_subject_management_edit():
    if request.method == 'POST':
        subject_id = request.form['subject_id']
        subject_code = request.form['subject_code']
        subject_name = request.form['subject_name']
        description = request.form['description']
        subject_type = request.form['subject_type']
        total_admission = request.form['total_admission']
        recommendation_admission = request.form['recommendation_admission']
        college_id = request.form['college_id']

        # 执行更新操作
        cursor = connection.cursor()
        cursor.execute('''
            UPDATE first_subject 
            SET subject_code = %s, subject_name = %s, description = %s, subject_type = %s, 
                total_admission = %s, recommendation_admission = %s, college_id = %s
            WHERE subject_id = %s
        ''', (subject_code, subject_name, description, subject_type, total_admission, recommendation_admission, college_id, subject_id))
        connection.commit()

        return redirect(url_for('first_subject_management'))  # 重定向到一级学科管理界面

    # 如果是GET请求，先查询现有学科信息
    subject_id = request.args.get('subject_id')
    cursor = connection.cursor()
    cursor.execute('''
        SELECT * FROM first_subject WHERE subject_id = %s
    ''', (subject_id,))
    subject = cursor.fetchone()

    # 将查询到的学科信息传递给模板
    return render_template('first_subject_management_edit.html', subject=subject)



@app.route('/mentor_management')
def mentor_management():
    return render_template('mentor_management.html')

@app.route('/get_college_names')
def get_college_names():
    query = request.args.get('query', '')
    sql = "SELECT college_name FROM college WHERE college_name LIKE %s"
    results = db_execute(sql, ('%' + query + '%',))
    college_names = [row['college_name'] for row in results]
    return jsonify(college_names)

@app.route('/second_subject_management')
def second_subject_management():
    # 处理二级学科管理的逻辑
    return render_template('second_subject_management.html')


def db_execute(query, params=()):
    with pymssql.connect(
    host='DESKTOP-M05GEV8',
    user='sa',
    password='123456',
    database='Task_1'
    ) as conn:
        with conn.cursor(as_dict=True) as cursor:
            cursor.execute(query, params)
            return cursor.fetchall()


app.secret_key = '123456'

if __name__ == '__main__':
    app.run(debug=True)
