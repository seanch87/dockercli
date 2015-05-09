#!/usr/bin/env python
from __future__ import unicode_literals
from __future__ import print_function

import sys
import shlex

from docker import AutoVersionClient
from docker.utils import kwargs_from_env
from docker.errors import APIError
from docker.errors import DockerException
from requests.exceptions import ConnectionError

from .options import allowed_args
from .options import parse_command_options
from .options import format_command_help


class DockerClient(object):
    """
    This client is a "translator" between docker-py API and
    the standard docker command line. We need one because docker-py
    does not use the same naming for command names and their parameters.
    For example, "docker ps" is named "containers", "-n" parameter
    is named "limit", some parameters are not implemented at all, etc.
    """

    def __init__(self):
        """
        Initialize the Docker wrapper.
        """

        self.handlers = {
            'help': (self.help, "Help on available commands."),
            'version': (self.version, "Equivalent of 'docker version'."),
            'ps': (self.containers, "Equivalent of 'docker ps'."),
            'images': (self.images, "Equivalent of 'docker images'."),
            'run': (self.run, "Equivalent of 'docker run'."),
            'rm': (self.rm, "Equivalent of 'docker rm'."),
            'search': (self.search, "Equivalent of 'docker search'."),
            'start': (self.start, "Equivalent of 'docker start'."),
            'stop': (self.not_implemented, "Equivalent of 'docker stop'."),
            'info': (self.info, "Equivalent of 'docker info'.")
        }

        self.is_stream = False
        self.output = None

        if sys.platform.startswith('darwin') \
                or sys.platform.startswith('win32'):
            try:
                # mac or win
                kwargs = kwargs_from_env()
                # hack from here:
                # http://docker-py.readthedocs.org/en/latest/boot2docker/
                # See also: https://github.com/docker/docker-py/issues/406
                kwargs['tls'].assert_hostname = False
                self.instance = AutoVersionClient(**kwargs)
            except DockerException as x:
                if 'CERTIFICATE_VERIFY_FAILED' in x.message:
                    raise DockerSslException(x)
                raise x
        else:
            # unix-based
            self.instance = AutoVersionClient(
                base_url='unix://var/run/docker.sock')

    def handle_input(self, text):
        """
        Parse the command, run it via the client, and return
        some iterable output to print out. This will parse options
        and arguments out of the command line and into parameters
        consistent with docker-py naming. It is designed to be the
        only really public method of the client. Other methods
        are just pass-through methods that delegate commands
        to docker-py.
        :param text: user input
        :return: iterable
        """
        tokens = shlex.split(text) if text else ['']
        cmd = tokens[0]
        params = tokens[1:] if len(tokens) > 1 else None

        self.is_stream = False

        if cmd and cmd in self.handlers:
            handler = self.handlers[cmd][0]

            if params:
                try:
                    if '-h' in tokens or '--help' in tokens:
                        self.output = [format_command_help(cmd)]
                    else:
                        parser, popts, pargs = parse_command_options(cmd, params)
                        if 'help' in popts:
                            del popts['help']

                        self.output = handler(*pargs, **popts)

                except APIError as ex:
                    self.is_stream = False
                    self.output = [ex.explanation]
                except Exception as ex:
                    self.is_stream = False
                    self.output = [ex.message]
            else:
                self.output = handler()
        else:
            self.output = self.help()

    def help(self, *args, **kwargs):
        """
        Collect and return help docstrings for all commands.
        :return: list of tuples
        """
        _, _ = args, kwargs

        help_rows = [(key, self.handlers[key][1])
                     for key in self.handlers.keys()]
        return help_rows

    def not_implemented(self, *args, **kwargs):
        """
        Placeholder for commands to be implemented.
        :return: iterable
        """
        _, _ = kwargs
        return ['Not implemented.']

    def version(self, *args, **kwargs):
        """
        Return the version. Equivalent of docker version.
        :return: list of tuples
        """
        _, _ = kwargs

        try:
            verdict = self.instance.version()
            result = [(k, verdict[k]) for k in sorted(verdict.keys())]
            return result
        except ConnectionError as ex:
            raise DockerPermissionException(ex)

    def info(self, *args, **kwargs):
        """
        Return the system info. Equivalent of docker info.
        :return: list of tuples
        """
        _, _ = kwargs

        rdict = self.instance.info()
        result = [(k, rdict[k]) for k in sorted(rdict.keys())]
        return result

    def containers(self, *args, **kwargs):
        """
        Return the list of containers. Equivalent of docker ps.
        :return: list of dicts
        """

        _ = args

        # Truncate by default.
        if 'trunc' in kwargs and kwargs['trunc'] is None:
            kwargs['trunc'] = True

        csdict = self.instance.containers(**kwargs)
        if len(csdict) > 0:

            if 'quiet' not in kwargs or not kwargs['quiet']:
                # Container names start with /.
                # Let's strip this for readability.
                for i in range(len(csdict)):
                    csdict[i]['Names'] = map(
                        lambda x: x.lstrip('/'), csdict[i]['Names'])

            return csdict
        else:
            return ['There are no containers to list.']

    def rm(self, *args, **kwargs):
        """
        Remove a container. Equivalent of docker rm.
        :param kwargs:
        :return: Container ID or iterable output.
        """

        result = []
        containers = args

        for container in containers:
            self.instance.remove_container(container, **kwargs)
            result.append(container)

        return result

    def run(self, *args, **kwargs):
        """
        Create and start a container. Equivalent of docker run.
        :param kwargs:
        :return: Container ID or iterable output.
        """
        if not args:
            return ['Image name is required.']

        kwargs['image'] = args[0]
        kwargs['command'] = args[1:] if len(args) > 1 else []

        runargs = allowed_args('run', **kwargs)
        result = self.instance.create_container(**runargs)

        if result:
            if "Warnings" in result and result['Warnings']:
                return [result['Warnings']]
            if "Id" in result and result['Id']:
                is_attach = 'detach' not in kwargs or not kwargs['detach']
                start_args = {
                    'container': result['Id'],
                    'attach': is_attach
                }
                return self.start(**start_args)
        return ['There was a problem running the container.']

    def start(self, **kwargs):
        """
        Start a container. Equivalent of docker start.
        :param kwargs:
        :return: Container ID or iterable output.
        """
        startargs = allowed_args('start', **kwargs)

        attached = None

        if kwargs['attach']:
            attached = self.attach(
                container=kwargs['container'],
                stream=True,
                stdout=True,
                stderr=False,
                logs=False)

        result = self.instance.start(**startargs)
        if result:
            return [result]
        elif attached:
            self.is_stream = True
            return attached
        else:
            return [kwargs['container']]

    def attach(self, **kwargs):
        """
        Attach to container STDOUT and / or STDERR.
        Docker-py does not allow attaching to STDIN.
        TODO: look at ways to attach to STDIN
        Equivalent of docker attach.
        :param kwargs:
        :return: Iterable output
        """
        self.is_stream = True
        result = self.instance.attach(**kwargs)
        return result

    def logs(self, **kwargs):
        """
        Retrieve container logs. Equivalent of docker logs.
        :param kwargs:
        :return: Iterable output
        """
        self.is_stream = True
        return self.instance.logs(**kwargs)

    def images(self, **kwargs):
        """
        Return the list of images. Equivalent of docker images.
        :return: list of dicts
        """

        result = self.instance.images(**kwargs)
        if len(result) > 0:
            return result
        else:
            return ['There are no images to list.']

    def search(self, **kwargs):
        """
        Return the list of images matching specified term.
        Equivalent of docker search.
        :return: list of dicts
        """

        result = self.instance.search(**kwargs)

        if len(result) > 0:
            for res in result:
                # Make results  more readable, like official CLI does.
                if 'is_trusted' in res:
                    res['is_trusted'] = '[OK]' if res['is_trusted'] else ''
                if 'is_official' in res:
                    res['is_official'] = '[OK]' if res['is_official'] else ''
            return result
        else:
            return ['No images were found.']


class DockerPermissionException(Exception):

    def __init__(self, inner_exception):
        self.inner_exception = inner_exception
        self.message = """You don't have the necessary permissions to call Docker API.
Try the following:

  # Add a docker group if it does not exist yet.
  sudo groupadd docker

  # Add the connected user "${USER}" to the docker group.
  # Change the user name to match your preferred user.
  sudo gpasswd -a ${USER} docker

  # Restart the Docker daemon.
  # If you are in Ubuntu 14.04, use docker.io instead of docker
  sudo service docker restart

You may need to reboot the machine.
"""


class DockerSslException(Exception):
    """
    Wrapper to handle SSL: CERTIFICATE_VERIFY_FAILED:
    https://github.com/docker/docker-py/issues/465
    """

    def __init__(self, inner_exception):
        self.inner_exception = inner_exception
        self.message = """Your version of requests library has a problem with OpenSSL.
Try the following:

  brew switch openssl 1.0.1j
"""
