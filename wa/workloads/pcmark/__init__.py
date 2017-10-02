#    Copyright 2014-2015 ARM Limited
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
import logging
import json
import re

from HTMLParser import HTMLParser
from collections import defaultdict, OrderedDict
from distutils.version import StrictVersion

from wa import ApkUiautoWorkload, Parameter
from wa.utils.types import list_of_strs, numeric
from wa.framework.exception import WorkloadError


class PCMark(ApkUiautoWorkload):

    name = 'pcmark'
    description = """
    Android benchmark designed by Qualcomm.

    PCMark began as a mobile web benchmarking tool that today has expanded
    to include three primary chapters. The Browser Chapter evaluates mobile
    web browser performance, the Multicore chapter measures the synergy of
    multiple CPU cores, and the Metal Chapter measures the CPU subsystem
    performance of mobile processors. Through click-and-go test suites,
    organized by chapter, PCMark is designed to evaluate: UX, 3D graphics,
    and memory read/write and peak bandwidth performance, and much more!

    Note: PCMark v3.0 fails to run on Juno

    """
    package_names = ['com.futuremark.pcmark.android.benchmark']
    versions=['2.0.3716']

    parameters = [
        Parameter('version', allowed_values=versions, default=versions[0],
                  description=('Specify the version of PCMark to be run. ')),
    ]


    def setup(self, context):
        self.gui.uiauto_params['version'] = self.version
        super(PCMark, self).setup(context)
