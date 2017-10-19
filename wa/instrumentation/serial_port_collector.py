#    Copyright 2017 ARM Limited
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#


# from devlib.utils.serial_port import get_serial_connection
from serial import Serial
from pexpect import fdpexpect

from wa import Instrument, Parameter
from wa.framework.instrumentation import very_slow
from wa.framework.exception import ConfigError

class SerialPortCollector(Instrument):
    name = 'serial-port-collector'

    descrption = """
    Collects the output of a serial port during workload execution
    """

    parameters = [
        Parameter('ports', default='/dev/ttyUSB0',
                  description='Path to serial ports to collect data from'),
        Parameter('baudrate', default=115200, kind=id,
                  description="""
                  Baudrate of port(s). If all ports have the same baudrate, this
                  an int. Otherwise, a dictionary mapping port paths to baudrates
                  """),
    ]

    connetion_timeout = 1

    def validate(self):
        if isinstance(self.baudrate, int):
            self.baudrate = {p: self.baudrate for p in self.ports}
        else:
            if not hasattr(self.baudrate, 'iteritems'):
                raise ConfigError(
                    'baudrate should be either int or 1-level dictionary. '
                    'Value is {}'.format(repr(self.baudrate)))

            for port, rate in self.baudrate.iteritems():
                if not isinstance(rate, int):
                    raise ConfigError('Baudrate for {} is {}, should be int'
                                      .format(port, type(rate)))

            missing_ports = set(self.ports) - set(self.baudrate.keys())
            if missing_ports:
                raise ConfigError('Baudrate not specified for ports {}'
                                  .format(missing_ports))

    def setup(self, context):
        self.log_files = {}
        for port in self.ports:
            name = 'serial_port_{}.log'.format(os.path.basename(port))
            path = os.path.join(context.output_directory, name)
            self.log_files[port] = open(path, 'w')

    @very_slow
    def start(self, context):
        self.pexpects = {}
        for port in self.ports:
            conn = Serial(port=port, baudrate=self.baudrate[port])
            self.pexpects[port] = fdpexpect(conn.fileno(),
                                            self.log_files[port])

    @very_slow
    def stop(self, context):
        for pexpect in self.pexpects.itervalues():
            pexpect.close()

    def update_result(self, context):
        for port in self.ports:
            context.add_artifact('serial_port_output',
                                 self.log_files[port].name, 'data',
                                 classifiers={'serial_port': port,
                                              'baudrate': self.baudrate[port]})
