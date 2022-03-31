import json
import os
from typing import Dict, List, Tuple
import re

import psutil


#######################################################
################### Node disk info ####################
#######################################################

class DiskStats:
    def __init__(self, total: int, used: int, available_to_root: int):
        self.total = total
        self.used = used
        self.available_to_root = available_to_root


def node_disk_stats() -> DiskStats:
    stats = os.statvfs("/")

    # Total space which is only available to root (unless changed at system level).
    total = stats.f_blocks * stats.f_frsize

    # Remaining free space is usable by root.
    available_to_root = stats.f_bfree * stats.f_frsize

    # Total space being used in general.
    used = total - available_to_root

    return DiskStats(
        total=total,
        used=used,
        available_to_root=available_to_root
    )


#######################################################
################ Containers disk info #################
#######################################################

kube_regex = re.compile(r"\d+:.+:/kubepods/[^/]+/pod([^/]+)/([0-9a-f]{64})")
docker_regex = re.compile(r"\d+:.+:/docker/pod([^/]+)/([0-9a-f]{64})")
other_regex = re.compile(r"\d+:.+:/docker/.*/pod([^/]+)/([0-9a-f]{64})")
other_regex2 = re.compile(r"\d+:.+:/kubepods/.*/pod([^/]+)/([0-9a-f]{64})")
other_regex3 = re.compile(
    r"\d+:.+:/kubepods\.slice/kubepods-[^/]+\.slice/kubepods-[^/]+-pod([^/]+)\.slice/docker-([0-9a-f]{64})"
)


def get_process_details(pid: int):
    # see https://man7.org/linux/man-pages/man7/cgroups.7.html
    cgroup_path = "/proc/%d/cgroup" % (pid,)

    if not os.path.isfile(cgroup_path):
        return None, None

    with open(cgroup_path, "r") as f:
        lines = f.readlines()
        for line in lines:
            match = (
                kube_regex.match(line)
                or docker_regex.match(line)
                or other_regex.match(line)
                or other_regex2.match(line)
                or other_regex3.match(line)
            )
            if match is not None:
                # pod, container
                return match.group(1).replace("_", "-"), match.group(2)
    return None, None


class DiskUtils:
    @staticmethod
    def get_size(dir_path: str) -> int:
        total_size = 0
        for root, dirs, files in os.walk(dir_path):
            if root == dir_path:  # skip procfs and host mount if they are present ({directory_path}/proc and {directory_path}/host)
                dirs[:] = [d for d in dirs if d not in ["proc", "host"]]

            for f in files:
                fp = os.path.join(root, f)
                if not os.path.islink(fp):  # skip if it is symbolic link
                    total_size += os.path.getsize(fp)

        return total_size


class ContainerDiskInfo:
    def __init__(self, container_id: str, pod_uid: str, disk_size: int):
        self.container_id = container_id
        self.pod_uid = pod_uid
        self.disk_size = disk_size


def get_pods_disk_info() -> Tuple[Dict[str, ContainerDiskInfo], List[str]]:
    # Create a dictionary of containers disk info by container id
    warnings: List[str] = []
    containers_map = {}
    for pid in psutil.pids():
        try:
            pod_uid, container_id = None, None # in case of an exception in `get_process_details`
            pod_uid, container_id = get_process_details(pid)
            if pod_uid is not None and container_id is not None and container_id not in containers_map:
                disk_size = DiskUtils.get_size(f"/proc/{pid}/root")
                containers_map[container_id] = ContainerDiskInfo(container_id, pod_uid, disk_size)
        except Exception as e:
            warnings.append(f"failed to extract information for process id {pid} (pod_uid={pod_uid}, container_id={container_id}): " + str(e))

    # Create a list of container from dictionary values
    containers: List[ContainerDiskInfo] = []
    for c in containers_map.values():
        containers.append(c)
    
    # Map pod ids to containers
    pods_to_containers = {}
    for c in containers:
        if c.pod_uid not in pods_to_containers:
            pods_to_containers[c.pod_uid] = []
        pods_to_containers[c.pod_uid].append(c)

    return pods_to_containers, warnings


#######################################################
#################### Main program #####################
#######################################################

def get_disk_info():
    # Calculate and format node disk stats
    disk_stats = node_disk_stats()
    disk_stats_json_obj = {
        "total": disk_stats.total,
        "used": disk_stats.used,
        "available_to_root": disk_stats.available_to_root
    }

    # Calculate and format pods disk distribution
    pods_disk_info, warnings = get_pods_disk_info()
    pods_distribution_json_obj = {
        "pods_distribution": [
            {
                "pod_uid": pod_uid,
                "containers": [{
                    "container_id": c.container_id,
                    "disk_size": c.disk_size
                } for c in containers]
            } for pod_uid, containers in pods_disk_info.items()
        ],
        "warnings": warnings
    }

    # Create and return an object that contains both the node disk stats and pods disk distribution
    json_obj = {
        "disk_stats": disk_stats_json_obj,
        "pods_disk_info": pods_distribution_json_obj
    }
    return json_obj


if __name__ == "__main__":
    info = get_disk_info()
    print(json.dumps(info))
