import csv
import os.path as osp
from functools import reduce

import configparser
import numpy as np
from scipy.optimize import fsolve

DECIMAL_PRECISION = 5


class Fond:
    def __init__(self):
        self.rows = []
        self.invested = []
        self.projected = []
        self.interests = []
        self.current_year = None
        self.filedir = osp.join(osp.dirname(osp.realpath(__file__)), "sheets")

    def load_sheet(self):
        data_file_path = osp.join(self.filedir, "chart.csv")
        with open(data_file_path, newline='') as datasheet:
            reader = csv.DictReader(datasheet)
            total_eingezahlt = 0
            year = None
            for row in reader:
                row_data = []
                eingezahlt = float(row['Eingezahlt'])
                total_eingezahlt += eingezahlt
                row_data.append(eingezahlt)
                self.invested.append(eingezahlt)
                row_data.append(float(row['Wert']))
                row_data.append(total_eingezahlt)
                year = row['Jahr']
                self.rows.append(row_data)
            self.current_year = year

    @staticmethod
    def zinsZins(invested, r):
        jahr = len(invested)
        return reduce((lambda x, y: y[1] * np.power(r, jahr - y[0] - 1) + x), enumerate(invested), 0) \
               + reduce((lambda x, y: 1.0 / 2 * y[1] * (r - 1) * np.power(r, jahr - y[0] - 1) + x), enumerate(invested),
                        0)

    @staticmethod
    def solver(invested, wert):
        func = lambda r: wert - Fond.zinsZins(invested, r)
        r_initial_guess = 1.1
        r_solution = fsolve(func, np.array([r_initial_guess], np.double))
        return r_solution[0]

    def calc_avg_interest(self):
        self.load_sheet()
        for i in range(len(self.rows)):
            invested = self.invested[:i + 1]
            wert = self.rows[i][1]
            interest = np.round(Fond.solver(invested, wert), DECIMAL_PRECISION).item() - 1
            self.interests.append(interest)

    def project(self, dynamic_factor, years):
        interest = fond.interests[-1]
        total_eingezahlt = self.rows[-1][-1]
        yearly_rate = self.rows[-1][0]
        r = interest + 1
        data_file_path = osp.join(self.filedir, f"Projected-{self.current_year}-{'{:.5f}'.format(interest)}.csv")
        with open(data_file_path, 'w', encoding='UTF8') as f:
            writer = csv.writer(f)
            header = ['Eingezahlt', 'Wert', 'Total Eingezahlt']
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

    def calculate(self, dynamic_factor, years):
        fond.calc_avg_interest()
        current_interest = fond.interests[-1]
        print("Current interest: " + '{:.5f}'.format(current_interest))
        fond.project(dynamic_factor, years)


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

fond = Fond()
fond.calculate(dynamic_factor, years)
