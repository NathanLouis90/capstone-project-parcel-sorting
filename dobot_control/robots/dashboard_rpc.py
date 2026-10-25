"""Use the launcher's existing dashboard connections for status and stop requests."""

from experiments.robot_home import parse_reply, status


class ExistingDashboard:
    def __init__(self, dashboard):
        self.dashboard = dashboard

    def command(self, command):
        return parse_reply(self.dashboard.sendRecvMsg(command), command)


def controller_status(dashboards):
    result = {}
    for arm, dashboard in dashboards.items():
        try:
            mode, alarms = status(ExistingDashboard(dashboard))
        except Exception as error:
            raise RuntimeError('{} controller status failed: {}'.format(arm, error)) from error
        result[arm] = dict(mode=mode, alarms=alarms)
    return result


def emergency_stop(dashboards):
    errors = []
    for arm, dashboard in dashboards.items():
        try:
            ExistingDashboard(dashboard).command('EmergencyStop()')
        except Exception as error:
            errors.append('{}: {}'.format(arm, error))
    if errors:
        raise RuntimeError('Stop acknowledgement failed: ' + '; '.join(errors))
    return True
