from flask import Flask, render_template, request, flash, redirect, url_for

import pymssql

app = Flask(__name__)

# 连接数据库
def get_db_connection():
    conn = pymssql.connect(server='(local)', database='Task_01')  #根据实际情况更改
    return conn

# 获取游标
connection = get_db_connection()
cursor = connection.cursor()

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
