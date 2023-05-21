import csv
import os.path as osp
from functools import reduce

import configparser
import numpy as np
from scipy.optimize import fsolve

DECIMAL_PRECISION = 5
DELIMITER = ';'

class Fond:
    def __init__(self, chart_name):
        self.rows = []
        self.headers = None
        self.invested = []
        self.projected = []
        self.interests = []
        self.net_cash_flows = []
        self.current_year = None
        self.chart_name = chart_name
        if '-y' in chart_name or '-yealy' in chart_name:
            self.monthly = False
        else:
            self.monthly = True
        self.initial_investment = 0
        self.filedir = osp.join(osp.dirname(osp.realpath(__file__)), "sheets")
        self.sheet_path = osp.join(self.filedir, f"{chart_name}.csv")

    def load_sheet(self):
        with open(self.sheet_path, newline='') as datasheet:
            reader = csv.DictReader(datasheet, delimiter=DELIMITER)
            year = None
            total_saving = 0
            for row in reader:
                if not row['year']:
                    continue
                if row['year'].startswith('#'):
                    continue
                if not self.headers:
                    self.headers = list(row.keys())
                year = int(row['year'])
                if year == 0:
                    first_saving = float(row['saving'])
                    total_saving += first_saving
                    if first_saving:
                        self.initial_investment = first_saving
                    continue
                row_data = []
                saving = float(row['saving'])
                total_saving += saving
                row_data.append(saving)
                self.invested.append(saving)
                if self.monthly:
                    # the savings over the year (virtually) booked at the end of the year and not subject for return
                    # therefore they should not be included in the final cashflow-out which is total value
                    cash_value = float(row['total_value']) - saving
                else:
                    # in a yearly savings regime the complete cashflow-out does not contain the new savings for the next
                    # period
                    cash_value = float(row['total_value'])
                """
                distribute cashflow equally between years
                """
                net_cash_flow = - saving
                self.net_cash_flows.append(net_cash_flow)
                row_data.append(cash_value)
                row_data.append(total_saving)
                row_data.append(float(row['total_value']))
                self.rows.append(row_data)
            self.current_year = year

    @staticmethod
    def zinsZins(invested, r):
        jahr = len(invested)
        return reduce((lambda x, y: y[1] * np.power(r, jahr - y[0] - 1) + x), enumerate(invested), 0) \
               + reduce((lambda x, y: 1.0 / 2 * y[1] * (r - 1) * np.power(r, jahr - y[0] - 1) + x), enumerate(invested),
                        0)

    @staticmethod
    def weighted_cashflow(ncf, irr):
        return reduce(lambda x, y: y[1] / np.power(irr, y[0] + 1) + x, enumerate(ncf), 0)

    @staticmethod
    def solver(invested, wert):
        func = lambda r: wert - Fond.zinsZins(invested, r)
        r_initial_guess = 1.1
        r_solution = fsolve(func, np.array([r_initial_guess], np.double))
        return r_solution[0]

    def solver_irr(self, ncf):
        func = lambda r: Fond.weighted_cashflow(ncf, r) - self.initial_investment
        sum = reduce(lambda x, y: abs(y) + x, ncf[:-1],0)
        if sum > ncf[-1]:
            irr_initial_guess = 0.9
        else:
            irr_initial_guess = 1.1
        irr_solution = fsolve(func, np.array([irr_initial_guess], np.double))
        return irr_solution[0]

    def calc_avg_interest(self):
        self.load_sheet()
        for i in range(len(self.net_cash_flows)):
            ncf = list(self.net_cash_flows[:i+1])
            ncf[-1] = self.rows[i][1] # cash out, equals the total portfolio value for that year
            print(f"cash-flow-out/total value for year {i+1}: {ncf[-1]}")
            if self.rows[i][3] == self.rows[i][2]:
                interest = 0
            else:
                interest = np.round(self.solver_irr(ncf), DECIMAL_PRECISION).item() - 1
            self.rows[i].append(interest)
            self.interests.append(interest)

    def save_results(self):
        headers = ['interest']
        outdir = osp.join(self.filedir, 'out')
        out = osp.join(outdir, f"{self.chart_name}.csv")
        with open(out, "w+") as write_sheet:
            write_sheet.write(";".join(headers) + "\n")
            for interest in self.interests:
                write_sheet.write('{:.4f}'.format(interest) + "\n")

    def project(self, dynamic_factor, years):
        interest = self.interests[-1]
        total_eingezahlt = self.rows[-1][-1]
        yearly_rate = self.rows[-1][0]
        r = interest + 1
        data_file_path = osp.join(self.filedir, f"Projected-{self.current_year}-{'{:.5f}'.format(interest)}.csv")
        with open(data_file_path, 'w', encoding='UTF8') as f:
            writer = csv.writer(f)
            header = ['saving', 'total_value', 'total_savings']
            row_data = [yearly_rate, round(Fond.zinsZins(self.invested, r), 2), round(total_eingezahlt, 2)]
            self.projected.append(row_data)
            writer.writerow(header)
            writer.writerow(row_data)
            for i in range(years):
                yearly_rate = round(yearly_rate * dynamic_factor, 2)
                invest = round(yearly_rate, 2)
                total_eingezahlt += invest
                row_data = [invest]
                self.invested.append(invest)
                row_data.append(round(Fond.zinsZins(self.invested, r), 2))
                row_data.append(round(total_eingezahlt, 2))
                writer.writerow(row_data)

    def calculate(self):
        fond.calc_avg_interest()
        current_interest = self.interests[-1]
        print("Current internal rate of return: " + '{:.5f}'.format(current_interest))
        portfolio = self.consistency_check()
        print("Plausibility analysis, current portfolio value assumung this constant interest: " + '{:.5f}'.format(portfolio))

    def consistency_check(self):
        interest = self.interests[-1]
        portfolio = self.initial_investment
        for row in self.rows:
            portfolio = portfolio * (interest + 1) + row[0]
        return portfolio

top_package_dir = osp.dirname(osp.abspath(__file__))
properties_path = osp.join(top_package_dir, 'parameters.cfg')
configParser = configparser.ConfigParser()
configParser.read(properties_path)

years = configParser.get('parameters', 'years', fallback=None)
if not years:
    years = input("How many years should the fund-fit be project?: ")
    print()
years = int(years)
dynamic_factor = configParser.get('parameters', 'dynamic_factor', fallback=None)
if not dynamic_factor:
    percent = input("What is the yearly increase of the savings in per cent? (e.g. 5 %): ")
    print()
    dynamic_factor = 1 + float(percent)/100
else:
    dynamic_factor = float(dynamic_factor)

fond = Fond(configParser.get('parameters', 'chartname', fallback=""))
fond.calculate()
#fond.project(dynamic_factor, years)
fond.save_results()
