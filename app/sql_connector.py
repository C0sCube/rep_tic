import mysql.connector
import traceback
from app.constants import conf_db, conf_sp


def fetch_symbol_mapping():
    
    try:
        db_config = conf_db()
        sp_config = conf_sp()
        
    except Exception:
        raise
    
    try:
        conn = mysql.connector.connect(**db_config)
        cursor = conn.cursor()
        
        nfo_sp = sp_config["nfo_symbol_mapper"]
        
        cursor.callproc(nfo_sp["name"], tuple(nfo_sp["params"]))

        mapping = {}

        for result in cursor.stored_results():
            columns = result.column_names
            for row in result.fetchall():
                record = dict(zip(columns, row))
                cogencis = record.get("cog_symbol")
                exchange = record.get("ex_symbol")
                if cogencis and exchange:
                    mapping[cogencis] = exchange

        return mapping

    except Exception:
        traceback.print_exc()
        raise

    finally:
        try:
            cursor.close()
            conn.close()
        except Exception:
            pass
