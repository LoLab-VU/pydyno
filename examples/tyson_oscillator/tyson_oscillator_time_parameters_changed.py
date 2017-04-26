import numpy as np

from pysb.examples.tyson_oscillator import model
from tropical.miscellaneous_analysis import change_parameter_in_time

tspan = np.linspace(0, 200, 200)

change_parameter_in_time(model, tspan, 51, 5, ['kp4'], 2)