#!/usr/bin/env python

# Copyright 2016 Canonical UK Limited
#
#    Licensed under the Apache License, Version 2.0 (the "License"); you may
#    not use this file except in compliance with the License. You may obtain
#    a copy of the License at
#
#         http://www.apache.org/licenses/LICENSE-2.0
#
#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS, WITHOUT
#    WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied. See the
#    License for the specific language governing permissions and limitations
#    under the License.

import os
import logging

from jinja2 import FileSystemLoader, Environment, exceptions

LOG = logging.getLogger(__name__)


class SnapFileRenderer():
    '''Helper class for rendering snap templates for runtime use'''

    def __init__(self):
        self._tmpl_env = Environment(
            loader=FileSystemLoader(os.path.join(os.environ.get('SNAP'),
                                                 'templates')),
            trim_blocks=True
        )

    def render(self, template_name, env):
        '''Render j2 template using SNAP environment context provided

        @param template_name: name of the template to use for rendering
        @param env: dict of variables to pass to the renderer
        @return: string of rendered data, ready to write back to a file
        '''
        try:
            template = self._tmpl_env.get_template(template_name)
        except exceptions.TemplateNotFound as te:
            LOG.error('Unable to locate template: {}'.format(template_name))
            raise te
        return template.render(env)