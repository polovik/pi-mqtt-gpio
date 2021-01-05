import os
import sys
import time
import logging
# import subprocess
from pi_mqtt_gpio.modules import GenericStream

WINDOWS = os.name == "nt"
LINUX = sys.platform.startswith("linux")
MACOS = sys.platform.startswith("darwin")

REQUIREMENTS = ("psutil",)
CONFIG_SCHEMA = {
    "monitor": {"type": "string", "required": True, "empty": False},
    "output_format": {"type": "string", "required": False, "empty": False},
    "partition_path": {"type": "string", "required": False, "empty": False},
    "device": {"type": "string", "required": False, "empty": False},
    "label": {"type": "string", "required": False, "empty": False},
}

_LOG = logging.getLogger("mqtt_gpio")

class Stream(GenericStream):
    
    def _calcCpuUsage(self, format):
        from psutil import cpu_times, cpu_count

        cpuTimes = cpu_times()
        curUser = cpuTimes.user
        curSystem = cpuTimes.system
        if LINUX:
            curIrq = cpuTimes.irq + cpuTimes.softirq
        elif WINDOWS:
            curIrq = cpuTimes.interrupt + cpuTimes.dpc
        curIdle = cpuTimes.idle
        
        elapsedUser = curUser - self.timeUser
        elapsedSystem = curSystem - self.timeSystem
        elapsedIrq = curIrq - self.timeIrq
        elapsedIdle = curIdle - self.timeIdle
        
        self.timeUser = curUser
        self.timeSystem = curSystem
        self.timeIrq = curIrq
        self.timeIdle = curIdle
        
        totalElapsed = elapsedUser + elapsedSystem + elapsedIrq + elapsedIdle
        if format == "user_space":
            return int(round(elapsedUser * 100 / totalElapsed / cpu_count()))
        elif format == "system_space":
            return int(round(elapsedSystem * 100 / totalElapsed / cpu_count()))
        elif format == "irq_space":
            return int(round(elapsedIrq * 100 / totalElapsed / cpu_count()))
        else: # "usage_percent"
            return int(round((totalElapsed - elapsedIdle) * 100 / totalElapsed / cpu_count()))
    
    def _calcMemoryUsage(self, format):
        from psutil import virtual_memory
        mem = virtual_memory()
        if format == "available_bytes":
            return mem.available
        elif format == "free_bytes":
            return mem.free
        elif format == "used_bytes":
            return mem.used
        else: # "percent"
            return mem.percent

    def _calcDiskUsage(self, format, partition):
        from psutil import disk_usage
        if WINDOWS:
            partition = partition + ":"
        disk = disk_usage(partition)
        if format == "total_bytes":
            return disk.total
        elif format == "free_bytes":
            return disk.free
        elif format == "used_bytes":
            return disk.used
        else: # "percentage"
            return disk.percent
        
    def _calcDiskActivity(self, format):
        from psutil import disk_io_counters
        # diskperf -y call on Windows one time
        activity = disk_io_counters(perdisk=False)
        lastRead = activity.read_bytes
        lastWrite = activity.write_bytes
    
        curRead = lastRead - self.bytesRead
        curWrite = lastWrite - self.bytesWrite
        totalBytes = curRead + curWrite
        
        self.bytesRead = lastRead
        self.bytesWrite = lastWrite
        
        if format == "read_bytes":
            return curRead
        elif format == "write_bytes":
            return curWrite
        else: # "total_bytes"
            return totalBytes
    
    def _calcTemperature(self, format, device, label = ''):
        temperature = -100;
        if LINUX:
            from psutil import sensors_temperatures
            allTemps = sensors_temperatures(fahrenheit = (format == "fahrenheit")) # "celsius"
            listTemps = allTemps.get(device, None)
            if listTemps:
                for entry in listTemps:
                    if entry.label == label:
                        temperature = entry.current
                        break
                _LOG.warning("couldn't found label", label, "for", device)
            else:
                _LOG.warning("couldn't get temperature for", device);
        elif WINDOWS:
            _LOG.warning("getting temperature hasn't implemented yet")
        return temperature
    
    def _calcTimeSinceBoot(self, format):
        from psutil import boot_time
        elapsedSeconds = int(time.time() - boot_time())
        if format == "minutes":
            return int(elapsedSeconds / 60)
        elif format == "hours":
            return int(elapsedSeconds / 60 / 60)
        else: # "seconds"
            return elapsedSeconds
        
    def __init__(self, config):
        self.timeUser = 0
        self.timeSystem = 0
        self.timeIrq = 0
        self.timeIdle = 0

        self.bytesRead = 0
        self.bytesWrite = 0
        
        _LOG.debug("__init__(config=%r)", config)
        MONITORS = {
            "cpu_usage": self._calcCpuUsage,
            "memory_usage": self._calcMemoryUsage,
            "disk_usage": self._calcDiskUsage,
            "disk_activity": self._calcDiskActivity,
            "temperature": self._calcTemperature,
            "uptime": self._calcTimeSinceBoot,
        }
        self.monitorFunction = MONITORS.get(config["monitor"], None)
        if self.monitorFunction:
            self.outputFormat = config.get("output_format", None)
            if not self.outputFormat:
                _LOG.warning("output monitor's format isn't specified for module systemstatus (config=%r)", config)
        else:
            _LOG.warning("invalid monitor type for module systemstatus (config=%r)", config)
            self.outputFormat = None
        self.partitionPath = config.get("partition_path", None)
        self.device = config.get("device", None)
        self.label = config.get("label", None)

    def setup_stream(self, config):
        _LOG.debug("setup_stream(config=%r)", config)

    def read(self, config):
        if not self.monitorFunction:
            _LOG.warning("monitor function is invalid for module systemstatus (config=%r)", config)
            return None
        if self.partitionPath:
            data = self.monitorFunction(self.outputFormat, self.partitionPath)
        elif self.device:
            data = self.monitorFunction(self.outputFormat, self.device, self.label)
        else:
            data = self.monitorFunction(self.outputFormat)
        _LOG.debug("status of %s = %s [%s]", config['name'], data, self.outputFormat)
        return str(data)
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
