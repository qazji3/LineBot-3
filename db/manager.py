import os

import urlparse
import psycopg2

class db_manager(object):

    def __init__(self, scheme, db_url):
        urlparse.uses_netloc.append(scheme)
        url = urlparse.urlparse(db_url)
        self.conn = psycopg2.connect(
            database=url.path[1:],
            user=url.username,
            password=url.password,
            host=url.hostname,
            port=url.port
        )
        self.cur = self.conn.cursor()


    # Table Exist

    def db_version(self):
        try:
            self.cur.execute('SELECT version();')
            db_version = self.cur.fetchone()
            conn.commit()
            return str(db_version)
        except psycopg2.Error as ex:
            self.close_connection()
            self.set_connection()
            return str(ex.message)
        except Exception as ex:
            return str(ex.message)


    def table_create(self):
        try:
            self.cur.execute('CREATE TABLE keyword_dict(\
                            id SERIAL,\
                            keyword VARCHAR(255),\
                            reply VARCHAR(255)\
                            );')
            conn.commit()
        except psycopg2.Error as ex:
            self.close_connection()
            self.set_connection()
            return str(ex.message)
        except Exception as ex:
            return str(ex.message)


    def table_exist(self):
        try:
            self.cur.execute('SELECT * FROM keyword_dict;')
            conn.commit()

            if self.cur.fetchone() is not None:
                return str(True)
            else:
                return str(False)
        except psycopg2.Error as ex:
            self.close_connection()
            self.set_connection()
            return str(ex.message)
        except Exception as ex:
            return str(ex.message)


    def insert_keyword(self, keyword, reply):
        try:
            self.cur.execute('INSERT INTO keyword_dict(keyword, reply)\
                              VALUES(' + keyword + ', ' + reply + ') RETURNING id;')
            conn.commit()

            return str(self.cur.fetchone()[0])
        except psycopg2.Error as ex:
            self.close_connection()
            self.set_connection()
            return str(ex.message)
        except Exception as ex:
            return str(ex.message)

    def sql_cmd(self, cmd):
        try:
            self.cur.execute(cmd)
            conn.commit()

            return str(self.cur.fetchone())
        except psycopg2.Error as ex:
            self.close_connection()
            self.set_connection()
            return str(ex.message)
        except Exception as ex:
            return str(ex.message)

    def close_connection(self):
        self.cur.close()

    def set_connection(self):
        self.cur = self.conn.cursor()