import json
import os
import pprint
from typing import Dict, Optional, List

import dpath.util
import psutil
from psutil._common import usage_percent


class DiskUtils:
    @staticmethod
    def get_size(directory_path) -> int:
        total_size = 0
        for dir_path, _, file_names in os.walk(directory_path):
            for f in file_names:
                fp = os.path.join(dir_path, f)
                # skip if it is symbolic link
                if not os.path.islink(fp):
                    total_size += os.path.getsize(fp)

        return total_size


class Container:
    container_dir: str
    id: str

    container_type: str
    container_name: Optional[str]
    pod_name: str
    pod_namespace: str

    disk_size: int

    def __init__(self, container_dir: str):
        self.container_dir = container_dir
        self.id = os.path.basename(container_dir)

        config = self._get_config()
        self.container_type = dpath.util.get(config, "annotations/io.kubernetes.cri.container-type")
        self.container_name = dpath.util.get(config, "annotations/io.kubernetes.cri.container-name", default=None)
        self.pod_name = dpath.util.get(config, "annotations/io.kubernetes.cri.sandbox-name")
        self.pod_namespace = dpath.util.get(config, "annotations/io.kubernetes.cri.sandbox-namespace")

        self.disk_size = self._get_disk_size()

    def _get_config(self):
        config_file_path = os.path.join(self.container_dir, "config.json")
        with open(config_file_path, "r") as config_file:
            json_config = config_file.read()
        return json.loads(json_config)

    def _get_disk_size(self) -> int:
        root_fs_dir = os.path.join(self.container_dir, "rootfs")
        return DiskUtils.get_size(root_fs_dir)

    def __repr__(self):
        return f"Container(container_type={self.container_type}, " \
               f"container_name={self.container_name}, disk_size={self.disk_size})"


class Pod:
    pod_name: str
    namespace: str

    def __init__(self, pod_name: str, namespace: str):
        self.pod_name = pod_name
        self.namespace = namespace

    def __eq__(self, other):
        return self.pod_name == other.pod_name and self.namespace == self.namespace

    def __hash__(self):
        return hash((self.pod_name, self.namespace))

    def __repr__(self):
        return f"Pod(pod_name={self.pod_name}, namespace={self.namespace})"


def get_pods_disk_distribution() -> (Dict[Pod, List[Container]], List[str]):
    partitions = psutil.disk_partitions(all=True)

    # Create a list of container objects
    warnings: List[str] = []
    containers: List[Container] = []
    for p in partitions:
        if not p.mountpoint.endswith("/rootfs"):
            continue

        container_dir = os.path.dirname(p.mountpoint)
        try:
            c = Container(container_dir)
            containers.append(c)
        except Exception as e:
            warnings.append(f"failed to get container information from {container_dir}: " + str(e))

    # Create a mapping between pods and the containers they host
    pods_to_containers: Dict[Pod, List[Container]] = {}
    for c in containers:
        pod = Pod(c.pod_name, c.pod_namespace)
        if pod not in pods_to_containers:
            pods_to_containers[pod] = []

        pods_to_containers[pod].append(c)

    return pods_to_containers, warnings


class DiskStats:
    total: int
    used: int
    available_to_root: int

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


def get_pod_distribution_info():
    # Calculate and format node disk stats
    disk_stats = node_disk_stats()
    disk_stats_json_obj = {
        "total": disk_stats.total,
        "used": disk_stats.used,
        "available_to_root": disk_stats.available_to_root
    }

    # Calculate and format pods disk distribution
    pods_distribution, warnings = get_pods_disk_distribution()
    pods_distribution_json_obj = {
        "pods_distribution": [
            {
                "pod_namespace": pod.namespace,
                "pod_name": pod.pod_name,
                "containers": [
                    {
                        "container_name": "__pause-container__" if c.container_type == "sandbox" else c.container_name,
                        "disk_size": c.disk_size
                    } for c in containers
                ]
            } for pod, containers in pods_distribution.items()
        ],
        "warnings": warnings
    }

    # Create and return an object that contains both the node disk stats and pods disk distribution
    json_obj = {
        "disk_stats": disk_stats_json_obj,
        "pods_disk_distribution": pods_distribution_json_obj
    }
    return json_obj


if __name__ == "__main__":
    info = get_pod_distribution_info()
    print(json.dumps(info))
