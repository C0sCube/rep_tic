import os
import re
import traceback
import calendar
from datetime import datetime, timezone, timedelta
from copyreg import add_extension
from app.sql_connector import fetch_symbol_mapping
from app.utils import Helper

EXCHANGE = "NSE"
DEFAULT_BIN_SIZE = 50
DEFAULT_NIL = "0"
 
class IndicesWriter:
    def __init__(self,logger:object,config:dict,output_path = str):
        
        #defaults
        self.exchange = "NSE"
        self.nil = DEFAULT_NIL
        self.config = config
        self.tick_bin = dict()
        self.error_indexes = []
        self.today_date = Helper.today_dt("%d-%m-%Y","Asia/Kolkata")
        self.today_month = Helper.today_dt("%B", "Asia/Kolkata").lower()
        self.bin_size = DEFAULT_BIN_SIZE
        
        #runtime helpers
        self.logger = logger
        self.utils = Helper()
        self.output_path = output_path
        
        self.ports = config["NSE_PORTS"]
        self.header = config["CSV_HEADER"]
        self.tick_ops = config["TICK_OPS"]
        self.header_count = len(self.header.split(","))
        

        self.content_size = 6
        self.symbol_index = 4

        
        # if add_extension:self.ext = CONFIG["INDEX_EXTENSIONS"].get("NSE", "")
        self.extension = config["INDEX_EXTENSIONS"][self.exchange]
        
        symbol_map = fetch_symbol_mapping()
        # if not symbol_map:
        #     self.logger.warning(
        #         "cls.__init__ -> No symbol mapping found. Using default"
        #     )
        #     symbol_map = config.get("NFO_SYMBOL_MAPPER", {})
        self.symbol_mapper = symbol_map
            
            
    def _generate_field_map(self, raw: str) -> dict:
        field_map = {}

        prt_spl = self.tick_ops["PORT_SPLIT"]
        val_spl = self.tick_ops["VAL_SPLIT"]
        
        for part in raw.split(prt_spl):
            part = part.strip()
            if not part or val_spl not in part:
                continue

            key, value = part.split(val_spl, 1)
            field_map[key] = value

        return field_map        
        
    def extract_tick_data(self, ticker: str):
        try:
            data_set = list()
            
            #split on
            # val_spl = self.tick_ops["PORT_SPLIT"]
            cpr_spl = self.tick_ops["SYM_SPLIT"]
            
            sections = ticker.split(cpr_spl)
            if len(sections) < self.content_size:
                return None, []

            *_,symbol, content = sections
        
            field_map = self._generate_field_map(content)
            #after fetching field_map , filter required data
            for port_name, port_val in self.ports.items():
                if port_name == "DATETIME":
                    value = field_map.get(port_val, "")
                    if value and " " in value:
                        date, time_ = value.split(" ", 1)
                    else:
                        date = time_ = self.nil

                    data_set.extend([date, time_])
                    continue

                value = field_map.get(port_val) or self.nil
                data_set.append(value)
            
            return symbol.strip(), data_set
        
        except Exception:
            raise

    def construct_symbol(self, _symbol):
        
        symbol = _symbol.strip()
        mapped = self.symbol_mapper.get(symbol, "")
        if not mapped:
            return symbol
        return f"{mapped}.{self.extension}"


    #TICK HANDLER : ENTRY POINT
    def process_ticker(self, ticker: str):

        # seperate symbol from tick data
        _symbol_, data = self.extract_tick_data(ticker.strip())
        if not _symbol_ or not data:
            return

        _symbol = self.construct_symbol(_symbol_)
            
        # bin activity required to flush the ticks
        if _symbol not in self.tick_bin:
            self.tick_bin[_symbol] = [self.header + "\n"] #header added
            
        self.tick_bin[_symbol].append(f"{_symbol},{",".join(data)}\n")

        #threshold
        if len(self.tick_bin[_symbol]) >= self.bin_size:
            self._flush_tick_data(_symbol)
        
    def _flush_tick_data(self, symbol):
        
        path = os.path.join(self.output_path,f"{symbol}.csv")
        
        flush_data = self.tick_bin.get(symbol, [])
        if flush_data:
            with open(path, mode="a", encoding="utf-8") as f:
                f.writelines(flush_data)
            self.tick_bin[symbol].clear()

    def flush_all_data(self):
        for symbol in list(self.tick_bin.keys()):
            self._flush_tick_data(symbol)    
        self.logger.info("Flushed ALL DATA.")