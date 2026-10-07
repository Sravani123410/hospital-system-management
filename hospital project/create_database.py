import pymysql

connection = pymysql.connect(
    host="localhost",
    user="root",
    password="Sravani@2005"
)

cursor = connection.cursor()

cursor.execute(
    "CREATE DATABASE IF NOT EXISTS hospital_db"
)

print("hospital_db database created successfully!")

cursor.close()
connection.close()