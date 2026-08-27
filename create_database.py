import pymysql


DB_HOST = "localhost"
DB_USER = "root"
DB_PASSWORD = ""
DB_NAME = "artisanlink"


try:
    connection = pymysql.connect(
        host=DB_HOST,
        user=DB_USER,
        password=DB_PASSWORD
    )

    cursor = connection.cursor()

    cursor.execute(
        f"CREATE DATABASE IF NOT EXISTS `{DB_NAME}` "
        "CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
    )

    connection.commit()

    print(f"✅ Database '{DB_NAME}' created successfully!")

except pymysql.MySQLError as error:
    print(f"❌ Database creation failed: {error}")

finally:
    if "connection" in locals() and connection.open:
        connection.close()