import csv
import math
import os.path as osp
from functools import reduce

import configparser
import numpy as np
from scipy.optimize import fsolve

DECIMAL_PRECISION = 5
DELIMITER = ';'


class Fond:
    def __init__(self, chart_name, early_booking=False):
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
        self.early_booking = early_booking
        self.filedir = osp.join(osp.dirname(osp.realpath(__file__)), "sheets")
        self.sheet_path = osp.join(self.filedir, f"{chart_name}.csv")

    def load_sheet(self):
        with open(self.sheet_path, newline='') as datasheet:
            reader = csv.DictReader(datasheet, delimiter=DELIMITER)
            year = None
            total_saving = 0
            readings = list(reader)
            readings = [x for x in readings if not (x['year'].startswith('#') or not x['year'])]
            for index, row in enumerate(readings):
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
                self.invested.append(saving)
                if index == 1 and self.early_booking:
                    self.initial_investment += saving
                if self.monthly:
                    if not self.early_booking:
                        # the savings over the year (virtually) booked at the end of the year and not subject for return
                        # therefore they should not be included in the final cashflow-out which is total value
                        cash_value = float(row['total_value']) - saving
                    else:
                        # saving were booked at the beginning of the interest period, therefore total value equals the
                        # cashflow
                        cash_value = float(row['total_value'])
                else:
                    # in a yearly savings regime the complete cashflow-out does not contain the new savings for the next
                    # period
                    cash_value = float(row['total_value']) - saving
                if index < len(readings) - 1:
                    if self.early_booking:
                        net_cash_flow = - float(readings[index + 1]['saving'])
                    else:
                        net_cash_flow = - saving
                else:
                    # has now meaning,
                    # the last cash flow entry will correspond to last portfolio value (minus saving)
                    net_cash_flow = 0
                row_data.append(saving)
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
        sum = reduce(lambda x, y: abs(y) + x, ncf[:-1], 0)
        if sum > ncf[-1]:
            irr_initial_guess = 0.9
        else:
            irr_initial_guess = 1.1
        irr_solution = fsolve(func, np.array([irr_initial_guess], np.double))
        return irr_solution[0]

    def time_weighted_rate_of_return(self):
        twror = 1
        pf_value = self.rows[0][-1] - self.rows[0][0]
        count = 1
        while pf_value == 0:
            pf_value = self.rows[count][-1] - self.rows[count][0]
            count += 1
        prev_portfolio_val = self.rows[count - 1][-1]
        for ind, row in enumerate(self.rows[count:]):
            pf_value_new = row[-1] - row[0]
            ret = pf_value_new / prev_portfolio_val
            twror = ret * twror
            prev_portfolio_val = row[-1]
            twrory = math.pow(twror, 1 / (ind + 1))
            self.interests.append(twrory)
        print("Current time-weighted rate of return: " + '{:.5f}'.format(self.interests[-1]))
        return self.interests[-1]

    def calc_internal_rate_of_return(self):
        for i in range(len(self.net_cash_flows)):
            ncf = list(self.net_cash_flows[:i + 1])
            ncf[-1] = self.rows[i][1]  # cash out, equals the portfolio value before the saving
            if self.rows[i][3] == self.rows[i][2]:
                interest = 0
            else:
                interest = np.round(self.solver_irr(ncf), DECIMAL_PRECISION).item() - 1
            self.rows[i].append(interest)
            self.interests.append(interest)
        logline = "Current internal rate of return"
        if self.early_booking:
            logline = logline + " with early booking"
        if self.irr_consistency_check():
            print(f"{logline}: " + '{:.5f}'.format(self.interests[-1]))
            return self.interests[-1]
        else:
            return None

    def save_results(self):
        headers = ['interest']
        outdir = osp.join(self.filedir, 'out')
        out = osp.join(outdir, f"{self.chart_name}.csv")
        with open(out, "w+") as write_sheet:
            write_sheet.write(";".join(headers) + "\n")
            for interest in self.interests:
                write_sheet.write('{:.4f}'.format(interest) + "\n")

    def project_zinsZins(self, dynamic_factor, years):
        # round(Fond.zinsZins(self.invested, r)
        pass

    def project_irr(self, dynamic_factor, years):
        interest = self.interests[-1]
        formula = lambda saving, pf: self.calculate_pf_after_year(pf, interest, saving)
        self.project(dynamic_factor, years, formula)

    def project(self, dynamic_factor, years, formula):
        interest = self.interests[-1]
        total_eingezahlt = self.rows[-1][2]
        invest = self.rows[-1][0]
        portfolio = self.rows[-1][-2]
        data_file_path = osp.join(self.filedir, f"Projected-{self.current_year}-{'{:.5f}'.format(interest)}.csv")
        with open(data_file_path, 'w', encoding='UTF8') as f:
            writer = csv.writer(f)
            header = ['year', 'saving', 'total_value', 'total_savings']
            row_data = [self.current_year, invest, portfolio, self.rows[-1][2]]
            self.projected.append(row_data)
            writer.writerow(header)
            writer.writerow(row_data)
            year = self.current_year
            for i in range(years):
                invest = round(invest * dynamic_factor, 3)
                total_eingezahlt += invest
                year += 1
                row_data = [year, invest]
                self.invested.append(invest)
                portfolio = formula(invest, portfolio)
                row_data.append(round(portfolio, 2))
                row_data.append(round(total_eingezahlt, 2))
                writer.writerow(row_data)

    def calculate(self):
        self.load_sheet()
        self.calc_internal_rate_of_return()
        # interest = self.time_weighted_rate_of_return()

    def irr_consistency_check(self):
        interest = self.interests[-1]
        if self.early_booking:
            portfolio = self.initial_investment * (1 + interest)
            years_counting = 1
        else:
            portfolio = self.initial_investment
            years_counting = 0
        for row in self.rows[years_counting:]:
            portfolio = self.calculate_pf_after_year(portfolio, interest, row[0])
        real_portfolio = self.rows[-1][-2]
        ratio = real_portfolio / portfolio
        return 1.01 > ratio > 0.99

    def calculate_pf_after_year(self, pf_before, interest, savings):
        if self.early_booking:
            # row[0] = accumulated savings of the year
            return (pf_before + savings) * (1 + interest)
        else:
            return pf_before * (interest + 1) + savings


def run_irr(fund, export=False, project=False):
    fund.calculate()
    if project:
        fund.project_irr(dynamic_factor, years)
    if export:
        fund.save_results()


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
    dynamic_factor = 1 + float(percent) / 100
else:
    dynamic_factor = float(dynamic_factor)

chartname = configParser.get('parameters', 'chartname', fallback="")
fond = Fond(chartname, early_booking=False)
run_irr(fond, export=True, project=True)
fond2 = Fond(chartname, early_booking=True)
run_irr(fond2)
