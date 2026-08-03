import psycopg2 as pg

def get_pgconnect():
    try:
        return pg.connect(
             host="localhost",
            database="postgres",
            user="postgres",
            password="Lipun@123",
            port="5432"
            )
    except:
        print("Database Could not connected")

        