
import os
import re
import traceback
import calendar
from datetime import datetime, timezone, timedelta
from copyreg import add_extension
from app.sql_connector import fetch_symbol_mapping
from app.utils import Helper
# from app.constants import 


EXCHANGE = "NFO"
DEFAULT_BIN_SIZE = 50
DEFAULT_NIL = "0"

class FutureOptionsWriter:
    def __init__(self,logger:object,config:dict,output_path:str):
        
        #defaults
        self.exchange = "NSF"
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
        
        #configs
        self.ports = config["NFO_PORTS"]
        self.header = config["CSV_HEADER"]
        self.tick_ops = config["TICK_OPS"]
        self.future_month_code = config["NFO_FUTURES"]
        self.month_codes = list(self.future_month_code.keys())
        self.inv_month_codes = {v: k for k, v in self.future_month_code.items()}

        
        #paths
        self.path_route = {
            "future":self.utils.create_dir(self.output_path,"Future"),
            "future_i":self.utils.create_dir(self.output_path,"Future","-I"),
            "future_ii":self.utils.create_dir(self.output_path,"Future","-II"),
            "future_iii":self.utils.create_dir(self.output_path,"Future","-III"),
            "option":self.utils.create_dir(self.output_path,"Option"),
            "spread":self.utils.create_dir(self.output_path,"Spread"),
            "other":self.utils.create_dir(self.output_path,"Other")
        }
        
        # regex
        self.regex = config["REGEX"]
        self.cregex = FutureOptionsWriter._compile_regexes(self.regex)
        
        # self._option_re = re.compile(r"^[A-Z0-9]+[CP][0-9]+\.NSF$",re.IGNORECASE) # Example: BANKNIFTYC24500.NSF
        # self._future_re = re.compile(r"^[A-Z0-9]+([FGHJKMNQUVXZ])[0-9]+\.NSF$",re.IGNORECASE) # Example: BANKNIFTYX24.NSF -> captures X
        # self._junk_re = re.compile(r"[A-Z]{3}\d{2}[A-Z]{3}\d{2}",re.IGNORECASE) # Catches malformed symbols
        
        # self.regex_feed_op = r"^([A-Z0-9]+)(\d{6})([CP])(\d+)\.NSF$"      # e.g. NMDC251028P70.NSF
        # self.regex_feed_fut = r"^([A-Z0-9]+)([FGHKMNQUVXZ])(\d{2})\.NSF$" # e.g. RECZ25.NSF

        
        self.future_suffix = {"future_i": "-I", "future_ii": "-II", "future_iii": "-III"}
        
        
        # if add_extension:
        self.extension = config["INDEX_EXTENSIONS"][self.exchange]
                
        symbol_map = fetch_symbol_mapping()
        # if not symbol_map:
        #     self.logger.warning(
        #         "cls.__init__ -> No symbol mapping found. Using default"
        #     )
        #     symbol_map = config.get("NFO_SYMBOL_MAPPER", {})
        self.symbol_mapper = symbol_map

    

    @staticmethod
    def _compile_regexes(regex_config: dict) -> dict:
        compiled = {
            name:re.compile(pattern, re.IGNORECASE)
            for name,pattern in regex_config.items()
        }
        return compiled
    

    @staticmethod
    def _check_if_fno_tick(symbol: str, ext: str) -> bool:
        return bool(symbol) and symbol.strip().endswith(f".{ext}")

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
                         
    def _check_tick_type(self, symbol):

        opt_regex = self.cregex["OPTION"]
        fut_regex = self.cregex["FUTURE"]
        sprd_regex = self.cregex["SPREAD"]

        month_code = self.inv_month_codes.get(self.today_month)
        if not month_code:
            self.logger.warning(f"Invalid month: {self.today_month}")
            return "other"

        if opt_regex.match(symbol):
            return "option"

        if sprd_regex.match(symbol):
            return "spread"

        if m := fut_regex.match(symbol):
            t_code = m.group(2)

            if t_code not in self.month_codes:
                return "future"

            offset = (self.month_codes.index(t_code) -
                    self.month_codes.index(month_code)) % 12

            future_order = ("future_i", "future_ii", "future_iii")
            return future_order[offset] if offset < 3 else "future"

        return "other"
      
    def extract_tick_data(self, ticker:str):
        try:
            data_set = list()
            
            #split on
            val_spl = self.tick_ops["PORT_SPLIT"]
            cpr_spl = self.tick_ops["CPR_SLIT"]
            
            other, content = ticker.split(val_spl,1)
            runtime, symbol = other.split(cpr_spl) #split of CPR ->runtime, symbol
            
            if not self._check_if_fno_tick(symbol.strip(), self.extension): 
                return None, []
            
            
            field_map = self._generate_field_map(content)
            #after fetching field_map , filter required data
            for port_name, port_val in self.ports.items():
                if port_name == "DATETIME":
                    data_set.extend([self.today_date,runtime])
                    continue
                    
                value = field_map.get(port_val, self.nil) or self.nil
                data_set.append(value)
            
            return symbol.strip(), data_set
        
        except Exception:
            raise
        
    def construct_symbol(self, _symbol: str) -> str:
        
        """
        Map the feed symbol from NSEEXCHAGE to COG symbol
        Classification into Future, Option and Contract is also handled.
        """
        symbol = _symbol.strip()

        # regex_feed_op = r"^([A-Z0-9]+)(\d{6})([CP])(\d+)\.NSF$"      # e.g. NMDC251028P70.NSF
        # regex_feed_fut = r"^([A-Z0-9]+)([FGHKMNQUVXZ])(\d{2})\.NSF$" # e.g. RECZ25.NSF
        opt_feed = self.cregex["OPT_FEED"]
        fut_feed = self.cregex["FUT_FEED"]
        crt_feed = self.cregex["SPR_FEED"]
        
        symbol_type = self._check_tick_type(symbol)

        if symbol_type == "option":
            match = re.match(opt_feed, symbol)
            if not match:
                return symbol, symbol_type
      
            undr, yymmdd, opt_type, strike = match.groups()
            underlying = self.symbol_mapper.get(undr, undr)

            try:
                dt = datetime.strptime(yymmdd, "%y%m%d")
                expiry = dt.strftime("%d%b%y").upper()  # e.g. 28OCT25
            except ValueError:
                self.logger.warning(f"Invalid Date in: {symbol}")
                self.error_indexes.append(f"Invalid Dt Frmt: {symbol}")
                return symbol,symbol_type

            return f"{underlying}{expiry}{strike}{opt_type}E.{self.extension}",symbol_type
                
            
        elif "future" in symbol_type:
            
            match = re.match(fut_feed, symbol)
            if not match:
                return symbol, symbol_type

            undr, t_code, year = match.groups()
            underlying = self.symbol_mapper.get(undr, undr)
            suffix = self.future_suffix.get(symbol_type, "")
            return f"{underlying}{suffix}.{self.extension}",symbol_type
            
        elif symbol_type == "contract":
            
            match = re.match(crt_feed, symbol)
            if not match:
                return symbol, symbol_type
                
            undr,spread = match.groups()
            underlying = self.symbol_mapper.get(undr, undr)
            return f"{underlying}{spread}.{self.extension}", symbol_type

        self.logger.warning(f"Unrecognized Symbol: {symbol}. Not Mapped.")
        self.error_indexes.append(symbol)
        return symbol,symbol_type
    
    #TICK HANDLER : ENTRY POINT
    def process_ticker(self, ticker: str):
        
        # seperate symbol from tick data
        _symbol_, data = self.extract_tick_data(ticker)
        if not _symbol_ or not data:
            return
        
        _symbol, symbol_type = self.construct_symbol(_symbol_)
        
        # bin activity required to flush the ticks
        combo_symbol = f"{_symbol}@{symbol_type}"
        if combo_symbol not in self.tick_bin: #unique
            self.tick_bin[combo_symbol] = [self.header + "\n"] #header added
            
        self.tick_bin[combo_symbol].append(f"{_symbol},{','.join(data)}\n")
        
        #threshold 
        if len(self.tick_bin[combo_symbol]) >= self.bin_size:
            self._flush_tick_data(combo_symbol)
      

    def _flush_tick_data(self, symbol):
        _symbol,category = symbol.split("@")
        base_path = self.path_route.get(category)
        path = os.path.join(base_path,f"{_symbol}.csv")
        
        flush_data = self.tick_bin.get(symbol, [])
        if flush_data:
            with open(path, mode="a", encoding="utf-8") as f:
                f.writelines(flush_data)
            self.tick_bin[symbol].clear()
    
    def flush_all_data(self):
        for symbol in list(self.tick_bin.keys()):
            self._flush_tick_data(symbol)    
        self.logger.info("Flushed ALL DATA.")
    
    
    
    #classifier
    # def __classify_futures_term(self, c_code, t_code):
    #     """ To Classify wether the code is Future I, II or III """
     
    #     month_codes = list(self.future_month_code.keys())
            
    #     if (c_code not in month_codes or t_code not in month_codes):
            
    #         self.logger.error(f"Invalid month code: {c_code} {t_code}")
    #         return "future"

    #     offset = (month_codes.index(t_code) - month_codes.index(c_code)) % 12
    #     return ["future_i", "future_ii", "future_iii"][offset] if offset < 3 else "future"    
    
    # def delete_junk_folder(self):
    #     import shutil
    #     path = self.path_route["other"]
    #     if os.path.isdir(path):
    #         shutil.rmtree(path)
    #         self.logger.info(f"Junk Deleted: {path}")
    #         return
    #     self.logger.info(f"{path} doesnt exist.")   

    #extract code
    #legacy 20260421
    #the structure of feed is changed
    #epoch time not necessarily is taken in 10= , take write time which is found initially
    
    # def extract_fields(self, ticker: str):
    #     data_set = [] 
    #     other,ticker_sections = ticker.strip().split(";",1)
    #     _time,symbol = other.split("CPR") 

    #     ditr = [kv.strip().split("=") for kv in ticker_sections.split(";") if kv.strip()]
    #     field_map = {k: v.strip() for k, v in ditr}
        
    #     data_set = []
    #     for port_name,port_val in self.ports.items():
    #         if port_name == "DATETIME":
    #             epoch_value = field_map.get(port_val, "")
    #             utc_dt = e.fromdatetimtimestamp(int(epoch_value), tz=timezone.utc)
    #             formatted_time = utc_dt.strftime("%d/%m/%Y %H:%M:%S")
    #             # print(formatted_time)
    #             value = str(formatted_time)    
                
    #             if value and " " in value:
    #                 date, time_ = value.split(" ", 1)
    #             else:
    #                 date,time_ = self.nil,self.nil  #value = "0,0" fallback
                    
    #             data_set.extend([date,time_])
    #         else:
    #             value = field_map.get(port_val, self.nil) or self.nil
    #             data_set.append(value)
        
    #     #Check if the tick is empty or not
    #     if all(i == self.nil for i in data_set[2:]): #first 2 are date, time
    #         self.logger.debug(f"cls.export_ports -> Empty tick skipped: {ticker}")
    #         return None,[]
        
    #     return symbol.strip(), data_set