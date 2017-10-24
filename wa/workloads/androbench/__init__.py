#    Copyright 2013-2015 ARM Limited
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

import os
import sqlite3

from wa import ApkUiautoWorkload
from wa.framework.exception import WorkloadError


class Androbench(ApkUiautoWorkload):
    name = 'androbench'
    description = """
    Measures the storage performance of an Android device.

    Website: http://www.androbench.org/wiki/AndroBench
    """
    package_names = ['com.andromeda.androbench2']
    phones_home = True

    def initialize(self, context):
        super(Androbench, self).initialize(context)
        if not self.target.is_rooted:
            raise WorkloadError('Androbench workload only works on rooted devices.')

    def setup(self, context):
        super(Androbench, self).setup(context)
        self.target.set_natural_rotation()

    def update_result(self, context):
        super(Androbench, self).update_result(context)
        dbn = 'databases/history.db'
        db = self.target.path.join(self.target.package_data_directory, self.package, dbn)
        host_results = os.path.join(context.output_directory, 'history.db')
        self.target.pull(db, host_results, as_root=True)
        qs = 'select * from history'
        conn = sqlite3.connect(host_results)
        c = conn.cursor()
        c.execute(qs)
        results = c.fetchone()
        context.add_metric('Sequential Read', results[8], 'MB/s')
        context.add_metric('Sequential Write', results[9], 'MB/s')
        context.add_metric('Random Read', results[10], 'MB/s')
        context.add_metric('Random Write', results[12], 'MB/s')
