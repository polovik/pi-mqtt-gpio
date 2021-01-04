import logging
import subprocess
from pi_mqtt_gpio.modules import GenericStream

# cross-platform library
# https://pypi.org/project/psutil/
REQUIREMENTS = ("psutil",)
CONFIG_SCHEMA = {
    "monitor": {"type": "string", "required": True, "empty": False},
}

_LOG = logging.getLogger("mqtt_gpio")

class Stream(GenericStream):
    def __init__(self, config):
        _LOG.debug("__init__(config=%r)", config)
        MONITORS = {
            "cpu_temperature": "cat /sys/class/thermal/thermal_zone0/temp",
            "gpu_temperature": "vcgencmd measure_temp",
            "memory_usage": "free",
            "cpu_usage": "cat /proc/stat",
            "disk_usage": "cat /proc/diskstats",
            "filesystem_usage": "df -h",
            "uptime": "cat /proc/uptime",
            "mqtt_server_state": "", # cpu and memory usage
        }

    def setup_stream(self, config):
        _LOG.debug("setup_stream(config=%r)", config)

    def read(self, config):
        # temperature: https://www.cyberciti.biz/faq/linux-find-out-raspberry-pi-gpu-and-arm-cpu-temperature-command/
        # GPU temperature: vcgencmd measure_temp
        # CPU temperature: cat /sys/class/thermal/thermal_zone0/temp and divide on 1000
        # CPU usage:
        # https://stackoverflow.com/questions/9229333/how-to-get-overall-cpu-usage-e-g-57-on-linux
        # grep 'cpu ' /proc/stat | awk '{usage=($2+$4)*100/($2+$4+$5)} END {print usage "%"}'
        # ps -A -o pcpu | tail -n+2 | paste -sd+ | bc
        # https://man7.org/linux/man-pages/man5/proc.5.html cat /proc/stat
        # decode information from /proc/stat - https://supportcenter.checkpoint.com/supportcenter/portal?eventSubmit_doGoviewsolutiondetails=&solutionid=sk65143
#        if not config["monitor"] in self.MONITORS:
#            _LOG.warning("invalid monitor type for stream read(config=%r)", config)
#            return "invalid monitor type: " + config["monitor"]
#        cmd = subprocess.run(config["monitor"], shell=true, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=1)
        cmd = subprocess.run('dir', shell=True, text=True, universal_newlines=True,
                              stdout=subprocess.PIPE, stderr=subprocess.STDOUT, 
                              encoding='CP866', timeout=1000)
#        res = cmd.stdout.splitlines()
        data = cmd.stdout
#        data = "'n"
#        data = data.join(data)
        _LOG.debug("read(config=%r, data=%s)", config, data)
        return data

    def write(self, config, data):
        _LOG.debug("write(config=%r,  data=%s)", config, data)

    def cleanup(self):
        pass
