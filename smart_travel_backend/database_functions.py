import mysql.connector

def create_database_connection():
    conn = mysql.connector.connect(
        host="localhost",
        user="root",
        password="12345",
        database="smart_travel_app_db"
    )
    return conn

def create_new_user(name,email,password):
    conn = create_database_connection()
    cursor = conn.cursor()

    query = "INSERT INTO users (name,email,password) VALUES (%s,%s,%s)"
    values = (name,email,password)

    cursor.execute(query, values)

    conn.commit()
    conn.close()

def db_login(email,password):
    conn = create_database_connection()
    cursor = conn.cursor()
    query="select * from users where email=%s and password= %s"
    cursor.execute(query,(email,password))
    user = cursor.fetchone()
    if user:
        return {"name": user[1],"email":user[2]}
    else:
        return None
