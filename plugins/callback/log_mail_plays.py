# -*- coding: utf-8 -*-

# https://github.com/ansible/ansible/blob/devel/lib/ansible/plugins/callback/log_plays.py
# (C) 2012, Michael DeHaan, <michael.dehaan@gmail.com>
# (c) 2017 Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# https://github.com/ansible/ansible/blob/devel/lib/ansible/plugins/callback/mail.py
# Copyright: (c) 2012, Dag Wieers <dag@wieers.com>
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

# https://github.com/ansible/ansible/blob/devel/lib/ansible/plugins/callback/logstash.py
# (C) 2016, Ievgen Khmelenko <ujenmr@gmail.com>
# (C) 2017 Ansible Project
# GNU General Public License v3.0+ (see COPYING or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import (absolute_import, division, print_function)
__metaclass__ = type

DOCUMENTATION = '''
    callback: log_mail_plays
    type: notification
    short_description: Save and email logs
    description:
      - This callback will save logs
      - This callback will email logs
    version_added: "2.7"
    requirements:
      - whitelisting in configuration
      - local log folder write permission
      - correct email (smtp) configuration
    options:
      log_folder:
        description: local log folder
        env:
          - name: LOG_MAIL_PLAYS_LOG_FOLDER
        ini:
          - section: callback_log_mail_plays
            key: log_folder
      smtp_server:
        description: Mail Transfer Agent, server that accepts SMTP
        env:
          - name: LOG_MAIL_PLAYS_SMTP_SERVER
        ini:
          - section: callback_log_mail_plays
            key: smtp_server
      smtp_port:
        description: Mail Transfer Agent Port, port at which server SMTP
        env:
          - name: LOG_MAIL_PLAYS_SMTP_PORT
        ini:
          - section: callback_log_mail_plays
            key: smtp_port
        default: 25
      smtp_auth:
        description: Mail Transfer Agent Authentication
        env:
          - name: LOG_MAIL_PLAYS_SMTP_AUTH
        ini:
          - section: callback_log_mail_plays
            key: smtp_auth
        default: False
      smtp_use_tls:
        description: Mail Transfer Agent use TLS mode
        env:
          - name: LOG_MAIL_PLAYS_SMTP_USE_TLS
        ini:
          - section: callback_log_mail_plays
            key: smtp_use_tls
        default: False
      smtp_username:
        description: Mail Transfer Agent Authentication Username
        env:
          - name: LOG_MAIL_PLAYS_SMTP_USERNAME
        ini:
          - section: callback_log_mail_plays
            key: smtp_username
      smtp_password:
        description: Mail Transfer Agent Authentication Password
        env:
          - name: LOG_MAIL_PLAYS_SMTP_PASSWORD
        ini:
          - section: callback_log_mail_plays
            key: smtp_password
      smtp_recipient:
        description: Mail recipient
        ini:
          - section: callback_log_mail_plays
            key: smtp_recipient
      smtp_sender:
        description: Mail sender
        ini:
          - section: callback_log_mail_plays
            key: smtp_sender
'''

import os
import json
import logging
import pprint
from datetime import datetime

import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
from email.utils import COMMASPACE, formatdate

from ansible.plugins.callback import CallbackBase


class CallbackModule(CallbackBase):
    """
    ansible log_mail_plays callback plugin
    ansible.cfg:
        callback_plugins   = <path_to_callback_plugins_folder>
        callback_whitelist = log_mail_plays
    and put the plugin in <path_to_callback_plugins_folder>

    Requires:
        
    This plugin makes use of the following environment variables:
    """

    CALLBACK_VERSION = 2.0
    CALLBACK_TYPE = 'notification'
    CALLBACK_NAME = 'log_mail_plays'
    CALLBACK_NEEDS_WHITELIST = True

    def __init__(self):
        super(CallbackModule, self).__init__()
        self.log_folder     = os.getenv('LOG_MAIL_PLAYS_FOLDER', './log_mail_plays')
        self.smtp_server    = os.getenv('LOG_MAIL_PLAYS_SMTP_SERVER')
        self.smtp_port      = os.getenv('LOG_MAIL_PLAYS_SMTP_PORT', 25)
        self.smtp_auth      = os.getenv('LOG_MAIL_PLAYS_SMTP_AUTH', False)
        self.smtp_use_tls   = os.getenv('LOG_MAIL_PLAYS_SMTP_USE_TLS', False)
        self.smtp_username  = None
        self.smtp_password  = None
        self.smtp_sender    = None
        self.smtp_recipient = None

    def set_options(self, task_keys=None, var_options=None, direct=None):
        super(CallbackModule, self).set_options(task_keys=task_keys, var_options=var_options, direct=direct)
        self.smtp_server    = self.get_option('smtp_server')
        self.smtp_port      = int(self.get_option('smtp_port'))
        self.smtp_auth      = bool(self.get_option('smtp_auth'))
        self.smtp_use_tls   = bool(self.get_option('smtp_use_tls'))
        self.smtp_username  = self.get_option('smtp_username')
        self.smtp_password  = self.get_option('smtp_password')
        self.smtp_sender    = self.get_option('smtp_sender')
        self.smtp_recipient = self.get_option('smtp_recipient')
        self.log_folder     = self.get_option('log_folder')
        self._mkdir(self.log_folder)

    def v2_playbook_on_start(self, playbook):
        self.playbook = playbook
        self.start_time = datetime.utcnow()
        self.log_filename = os.path.join(self.log_folder, self.playbook._file_name + self.start_time.strftime('_%Y-%m-%dT%H:%M:%S.log'))

        # reset logging config (new log filename for each new playbook start)
        self.logger = logging.getLogger()
        handler = logging.FileHandler(self.log_filename)
        formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(formatter)
        self.logger.addHandler(handler)
        
        data = {
            'status': "OK",
            # 'host': self.hostname,
            # 'session': self.session,
            'ansible_type': "start",
            'ansible_playbook': self.playbook,
        }

        logging.getLogger().info("ansible start", extra=data)

    def v2_playbook_on_stats(self, stats):
        end_time = datetime.utcnow()
        runtime = end_time - self.start_time
        summarize_stat = {}
        for host in stats.processed.keys():
            summarize_stat[host] = stats.summarize(host)

        data = {
            # 'status': status,
            # 'host': result._host.get_name(),
            # 'session': self.session,
            'ansible_type': "finish",
            'ansible_playbook': self.playbook,
            'ansible_playbook_duration': runtime.total_seconds(),
            'ansible_result': json.dumps(summarize_stat),
        }
        logging.getLogger().info("ansible stats", extra=data)

        if self.smtp_server:
            self.send_mail(
                send_from=self.smtp_sender, 
                send_to=self.smtp_recipient, 
                subject="Playbook:" + self.playbook._file_name + " finished", 
                message=pprint.pformat(summarize_stat), 
                files=[self.log_filename], 
                server=self.smtp_server,
                port=self.smtp_port,
                username=self.smtp_username,
                password=self.smtp_password,
                auth=self.smtp_auth,
                use_tls=self.smtp_use_tls)

    def v2_runner_on_ok(self, result, **kwargs):
        data = {
            'status': "OK",
            'host': result._host.get_name(),
            # 'session': self.session,
            'ansible_type': "task",
            'ansible_playbook': self.playbook,
            'ansible_host': result._host.name,
            'ansible_task': result._task,
            'ansible_result': self._dump_results(result._result)
        }
        logging.getLogger().info("ansible ok", extra=data)

    def v2_runner_on_skipped(self, result, **kwargs):
        data = {
            'status': "SKIPPED",
            'host': result._host.get_name(),
            # 'session': self.session,
            'ansible_type': "task",
            'ansible_playbook': self.playbook,
            'ansible_task': result._task,
            'ansible_host': result._host.name
        }
        self.logger.info("ansible skipped", extra=data)

    def v2_playbook_on_import_for_host(self, result, imported_file):
        data = {
            'status': "IMPORTED",
            'host': result._host.get_name(),
            'session': self.session,
            'ansible_type': "import",
            'ansible_playbook': self.playbook,
            'ansible_host': result._host.name,
            'imported_file': imported_file
        }
        self.logger.info("ansible import", extra=data)

    def v2_playbook_on_not_import_for_host(self, result, missing_file):
        data = {
            'status': "NOT IMPORTED",
            'host': result._host.get_name(),
            'session': self.session,
            'ansible_type': "import",
            'ansible_playbook': self.playbook,
            'ansible_host': result._host.name,
            'missing_file': missing_file
        }
        self.logger.info("ansible import", extra=data)

    def v2_runner_on_failed(self, result, **kwargs):
        data = {
            'status': "FAILED",
            'host': result._host.get_name(),
            # 'session': self.session,
            'ansible_type': "task",
            'ansible_playbook': self.playbook,
            'ansible_host': result._host.name,
            'ansible_task': result._task,
            'ansible_result': self._dump_results(result._result)
        }
        self.logger.error("ansible failed", extra=data)

    def v2_runner_on_unreachable(self, result, **kwargs):
        data = {
            'status': "UNREACHABLE",
            'host': result._host.get_name(),
            'session': self.session,
            'ansible_type': "task",
            'ansible_playbook': self.playbook,
            'ansible_host': result._host.name,
            'ansible_task': result._task,
            'ansible_result': self._dump_results(result._result)
        }
        self.logger.error("ansible unreachable", extra=data)

    def v2_runner_on_async_failed(self, result, **kwargs):
        data = {
            'status': "FAILED",
            'host': result._host.get_name(),
            'session': self.session,
            'ansible_type': "task",
            'ansible_playbook': self.playbook,
            'ansible_host': result._host.name,
            'ansible_task': result._task,
            'ansible_result': self._dump_results(result._result)
        }
        self.logger.error("ansible async", extra=data)

    def _mkdir(self, newdir):
        """works the way a good mkdir should :)
            - already exists, silently complete
            - regular file in the way, raise an exception
            - parent directory(ies) does not exist, make them as well
        """
        if os.path.isdir(newdir):
            pass
        elif os.path.isfile(newdir):
            raise OSError("a file with the same name as the desired " \
                        "dir, '%s', already exists." % newdir)
        else:
            head, tail = os.path.split(newdir)
            if head and not os.path.isdir(head):
                _mkdir(head)
            if tail:
                os.mkdir(newdir)

    def send_mail(self, send_from, send_to, subject, message, files=[],
                server="localhost", port=587, username='', password='',
                auth=False, use_tls=False):
        """Compose and send email with provided info and attachments.

        Args:
            send_from (str): from name
            send_to (str): to name
            subject (str): message title
            message (str): message body
            files (list[str]): list of file paths to be attached to email
            server (str): mail server host name
            port (int): port number
            username (str): server auth username
            password (str): server auth password
            use_tls (bool): use TLS mode
        """
        msg = MIMEMultipart()
        msg['From'] = send_from
        msg['To'] = COMMASPACE.join(send_to.split(','))
        msg['Date'] = formatdate()
        msg['Subject'] = subject

        msg.attach(MIMEText(message))

        for path in files:
            part = MIMEBase('application', "octet-stream")
            with open(path, 'rb') as file:
                part.set_payload(file.read())
            encoders.encode_base64(part)
            part.add_header('Content-Disposition',
                            'attachment; filename="{}"'.format(os.path.basename(path)))
            msg.attach(part)

        smtp = smtplib.SMTP(server, port)
        if use_tls:
            smtp.starttls()
        if auth:
            smtp.login(username, password)
        smtp.sendmail(send_from, send_to, msg.as_string())
        smtp.quit()
