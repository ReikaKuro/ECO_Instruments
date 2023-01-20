import json
import re
import time
import winrm.exceptions
from winrm.protocol import Protocol
from ping3 import ping
# import taf.pdu <-- find or create module that will communicate with GUDE PDU via SNMP
import threading
import logging
from logging.handlers import RotatingFileHandler
import sys
import socket
import datetime


class SetupInfo:
    def __init__(self, mapped_setup):

        self.instrument_pdu = mapped_setup[0][0]
        self.sa_info = mapped_setup[0][1]
        self.sg_info = mapped_setup[0][2]
        self.pcs_info = mapped_setup[1]

        self.any_occupied = False
        # find or create module that will communicate with GUDE PDU via SNMP
        self.pdu_controller = 0 #taf.pdu.interface.pdu()
        # self.pdu_controller.setup_pdu(model='GUDE', version='8220-1', host=self.instrument_pdu)

        self.is_logged_in = None
        self.idle = None
        self.shell_id_evaluation = True

        self.wait_before_turn_off_pdu = 360

    def ping_instrument(self, ip, count):
        logging.info(f'Pinging to {ip}')
        try:
            for c in range(count):
                time.sleep(1)
                if not type(ping(ip)) is float:
                    logging.info(f'SA/SG {ip} is not pingable')
                    # Just in case wait another 15 secoond
                    time.sleep(15)
                    return False
            logging.info(f'SA/SG {ip} is pingable')
            return True
        except Exception as e:
            logging.warning(f'{e} (IP: {ip}')

    def get_setup_user_idle_info(self):
        for u, _ in enumerate(self.pcs_info):
            ip = self.pcs_info[u][0]

            p = Protocol(
                endpoint='https://' + ip + ':5986/wsman',
                transport='ntlm',
                username=self.pcs_info[u][1],
                password=self.pcs_info[u][2],
                read_timeout_sec=4,
                operation_timeout_sec=2,
                server_cert_validation='ignore')

            self.shell_id_evaluation = True

            logging.info(f'Opening shell {ip}')
            try:
                shell_id = p.open_shell()

            except Exception as e:
                self.shell_id_evaluation = False
                logging.warning(f"Shell evaluation for {ip} did not pass. Skipping rest. {e}")

            except winrm.exceptions.InvalidCredentialsError as e:
                self.shell_id_evaluation = False
                logging.warning(e)

            if self.shell_id_evaluation:
                command_id = p.run_command(shell_id, 'query user', [])
                std_out, std_err, status_code = p.get_command_output(shell_id, command_id)
                std_out = std_out.decode('UTF-8')
                x = re.search(r'(\d+)\s+(Active|Disc)\s+([\d.:+]+)', std_out)

                self.is_logged_in = x.group(2)
                self.idle = x.group(3)

                if self.idle == '.' or not self.idle.__contains__('+' and ':'):
                    self.any_occupied = True
                    logging.info(
                        f'Getting info about setup {ip}, isLoggedIn = {self.is_logged_in}, idle time = {self.idle} , IsOccupied = {self.any_occupied}')
                    p.cleanup_command(shell_id, command_id)
                    p.close_shell(shell_id)
                    break

                else:
                    if self.is_logged_in == "Active":
                        self.any_occupied = True
                        logging.info(
                            f'Getting info about setup {ip}, isLoggedIn = {self.is_logged_in}, idle time = {self.idle} , IsOccupied = {self.any_occupied}')

                        p.cleanup_command(shell_id, command_id)
                        p.close_shell(shell_id)
                        break
                logging.info(
                    f'Getting info about {ip}, isLoggedIn = {self.is_logged_in}, idle time = {self.idle} , IsOccupied = {self.any_occupied}')

                p.cleanup_command(shell_id, command_id)
                p.close_shell(shell_id)

    def turn_off_instrument(self, instr_ip, instr_type, scpi_port):
        if instr_type == 'RS':
            try:
                so = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                so.connect((instr_ip, int(scpi_port)))
                so.sendall(":SYSTem:SHUTdown\n".encode())
                so.close()
                logging.info(f"Shutdown command was sent to {instr_type} [{instr_ip}]\n")
            except Exception as e:
                logging.error(f'Error {e}')

        elif instr_type == 'KS':
            try:
                so = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                so.connect((instr_ip, int(scpi_port)))
                so.sendall(":SYSTem:PDOWn\n".encode())
                so.close()
                logging.info(f"Shutdown command was sent to {instr_type} [{instr_ip}]\n")
            except Exception as e:
                logging.error(f'Error {e}')
        else:
            logging.error(f"Instrument vendor not recognized {instr_type}. Only R&S (RS) or Keysight (KS) acceptable.")

            return self.ping_instrument(instr_ip, 30)

    def pdu_switch_off(self, port):
        logging.info(f'Turning off pdu for {self.instrument_pdu}, {port}')
        self.pdu_controller.power_off(int(port))

    def monitor_setup(self):
        if self.ping_instrument(self.sa_info[0], 5):
            self.get_setup_user_idle_info()
            if not self.any_occupied:
                if not self.turn_off_instrument(self.sa_info[0], self.sa_info[2], self.sa_info[3]):
                    logging.warning(f'Turning off instrument did not work')
                else:
                    time.sleep(self.wait_before_turn_off_pdu)
                    self.pdu_switch_off(self.sa_info[1])

        if self.ping_instrument(self.sg_info[0], 5):
            if not self.any_occupied:
                self.get_setup_user_idle_info()
                if not self.turn_off_instrument(self.sg_info[0], self.sg_info[2], self.sg_info[3]):
                    logging.warning(f'Turning off instrument did not work')
                else:
                    self.pdu_switch_off(self.sg_info[1])


def load_json_file():
    """
    Opens json file with mapped setups
    :return: mapped setups in form of dictionary
    """
    with open('Setups.json', 'r') as f:
        setups_json = json.load(f)

    return setups_json


def parse_json_file(setups_file):
    """
    Takes argument in form json file parsed into dictionary
    :param setups_file: contains mapped setups in form of dictionary

    :return: Mapped setups in form of list which contains elements needed to create object SetupInfo()
    """
    setups_json = setups_file
    list_of_setups = []

    for setup_keyword in setups_json['setups']:
        instruments = [
            setups_json['setups'][setup_keyword]["instruments"]["pdu"],
            [
                setups_json['setups'][setup_keyword]["instruments"]["SA"]["ip"],
                setups_json['setups'][setup_keyword]["instruments"]["SA"]["port"],
                setups_json['setups'][setup_keyword]["instruments"]["SA"]["type"],
                setups_json['setups'][setup_keyword]["instruments"]["SA"]["scpi_port"]
            ],
            [
                setups_json['setups'][setup_keyword]["instruments"]["SG"]["ip"],
                setups_json['setups'][setup_keyword]["instruments"]["SG"]["port"],
                setups_json['setups'][setup_keyword]["instruments"]["SG"]["type"],
                setups_json['setups'][setup_keyword]["instruments"]["SG"]["scpi_port"]
            ]
        ]

        pcs_list = []
        for p, pcs_keyword in enumerate(setups_json["setups"][setup_keyword]["PCs"]):
            pc_list = [setups_json["setups"][setup_keyword]["PCs"][pcs_keyword]["ip"],
                       setups_json["setups"][setup_keyword]["PCs"][pcs_keyword]["login"],
                       setups_json["setups"][setup_keyword]["PCs"][pcs_keyword]["password"]]
            pcs_list.append(pc_list)

        mapped_setup = [instruments, pcs_list]

        list_of_setups.append(SetupInfo(mapped_setup))

    return list_of_setups


if __name__ == "__main__":
    file_handler = RotatingFileHandler(filename='Eco_Instruments_LOGS.log', encoding='utf8', maxBytes=52428800,
                                       backupCount=2)
    stdout_handler = logging.StreamHandler(stream=sys.stdout)
    handlers = [file_handler, stdout_handler]

    logging.basicConfig(
        level=logging.INFO,
        datefmt='%Y-%m-%d-%H:%M:%S',
        format='%(levelname)s %(asctime)s: %(message)s',
        handlers=handlers,
    )
    logging.info('Setup Monitor is running... better catch it before it run away :)')
    setups = load_json_file()
    setups_list = parse_json_file(setups)

    while True:
        start = time.perf_counter()
        threads = []

        # Set here time when script have to not work
        if not 6 <= int(datetime.datetime.today().hour) <= 20:
            for i in range(len(setups_list)):
                t = threading.Thread(target=setups_list[i].monitor_setup())
                t.start()
                threads.append(t)

            for thread in threads:
                thread.join()
        else:
            logging.info(f'{datetime.datetime.today().strftime("%H:%M:%S")} is out of working timeframe')

        finish = time.perf_counter()

        logging.info(f'Finished in {round(finish - start, 2)} seconds(s)')
        time.sleep(600)
