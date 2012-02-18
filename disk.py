from conversion import *
#from partition import *
import os

disk_features = {
    1 : 'EXTENDED',
    2 : 'PARTITION_NAME'
}

alignment_any = PedAlignment(0, 1)

class DiskError(Exception):
    pass

class Disk(object):
    def __init__(self, device=None, disk=None):
        if device:
            self.__device = device._Device__device
            self.__disk = disk_new(self.__device)
        elif disk:
            self.__disk = disk
            self.__device = self.__disk.contents.dev
        else:
            raise Exception("Dude WTF?")

    @property
    def type_name(self):
        return self.__disk.contents.type.contents.name

    @property
    def type_features(self):
        feat = self.__disk.contents.type.contents.features
        return disk_features[feat]

    @property
    def block_sizes(self):
        return self.__disk.contents.block_sizes

    @property
    def needs_clobber(self):
        return bool(self.__disk.contents.needs_clobber)

    @property
    def update_mode(self):
        return bool(self.__disk.contents.update_mode)

    def partitions(self):
        partitions = []
        part = disk_next_partition(self.__disk, None)

        while part:
            if part.contents.type == 4 or \
                part.contents.type == 8 or \
                part.contents.type == 10:
                part = disk_next_partition(self.__disk, part)
                continue
            p = Partition(part=part)
            partitions.append(p)
            part = disk_next_partition(self.__disk, part)

        return partitions

    def add_partition(self, part, alignment=None):
        try:
            p = self.get_partition(part.num)
            if p.geom == part.geom:
                raise DiskError
        except DiskError:
            raise ValueError("This partition already exists in the disk... And yeah, my english sucks.")
        except ValueError:
            pass
        partition = part._Partition__partition
        disk = self.__disk
        start, end, length = part.geom
        range_start = geometry_new(self.__device, start, 1)
        range_end = geometry_new(self.__device, end, 1)
        user_constraint = constraint_new(alignment_any, alignment_any, range_start, range_end, 1, length)
        if not bool(user_constraint):
            raise Exception("Could not set user defined constraint.")
        if alignment == 'optimal':
            dev_constraint = device_get_optimal_aligned_constraint(self.__device)
        elif alignment == 'minimal':
            dev_constraint = device_get_optimal_aligned_constraint(self.__device)
        elif alignment == None:
            dev_constraint = device_get_constraint(self.__device)
        else:
            raise ValueError("Alignment '%s' is not valid" % str(alignment))
        if not bool(dev_constraint):
            raise Exception("Could not set user defined constraint.")
        final_constraint = constraint_intersect(user_constraint, dev_constraint)
        constraint_destroy(user_constraint)
        constraint_destroy(dev_constraint)
        if not bool(final_constraint):
            raise Exception("Could not set device constraint.")
        added = disk_add_partition(disk, partition, final_constraint)
        print "Added val is:\n"
        print added
        constraint_destroy(final_constraint)
        if not added:
            disk_remove_partition(disk, partition)
            raise Exception("Failed to add partition")
        if part.name:
            set_name = partition_set_name(partition, part.name)
            if not set_name:
                disk_remove_partition(disk, partition)
                raise Exception("Failed to set partition name.")

    def delete_partition(self, part=None, part_num=None):
        if part and isinstance(part, Partition):
            partition = part._Partition__partition
        elif part_num:
            partition = self._get_ped_partition(part_num)
        else:
            raise ValueError("You must specify a Partition instance or a partition number.")
        if partition_is_busy(partition):
            raise Exception("Partition is busy, no sexy time for you!")
        disk_delete_partition(self.__disk, partition)
        self.commit()
        disk_destroy(self.__disk)
        self.__disk = disk_new(self.__device)

    def delete_all(self):
        disk_delete_all(self.__disk)
        return

    def commit(self):
        to_dev = disk_commit_to_dev(self.__disk)
        if not to_dev:
            raise Exception("Failed to commit disk changes to device.")
        to_os = disk_commit_to_os(self.__disk)
        if not to_os:
            raise Exception("Failed to commit disk changes to OS.")

    def _get_ped_partition(self, part_num):
        partition = disk_get_partition(self.__disk, part_num)
        if not bool(partition):
            raise ValueError("Partition number %i does not exist." % part_num)
        return partition

    def get_partition(self, part_num):
        partition = Partition(part=self._get_ped_partition(part_num))
        return partition

partition_type = {
    0 : 'NORMAL',
    1 : 'LOGICAL',
    2 : 'EXTENDED',
    4 : 'FREESPACE',
    8 : 'METADATA',
    10 : 'PROTECTED'
}

size_units = {
    "B":    1,       # byte
    "KB":   1000**1, # kilobyte
    "MB":   1000**2, # megabyte
    "GB":   1000**3, # gigabyte
    "TB":   1000**4, # terabyte
    "PB":   1000**5, # petabyte
    "EB":   1000**6, # exabyte
    "ZB":   1000**7, # zettabyte
    "YB":   1000**8, # yottabyte
    "KiB":  1024**1, # kibibyte
    "MiB":  1024**2, # mebibyte
    "GiB":  1024**3, # gibibyte
    "TiB":  1024**4, # tebibyte
    "PiB":  1024**5, # pebibyte
    "EiB":  1024**6, # exbibyte
    "ZiB":  1024**7, # zebibyte
    "YiB":  1024**8, # yobibyte
    "%":    1        # Fuck you pyparted, we've got percents!!!
}

class Size(object):
    def __init__(self, length, units="MB"):
        self.__length = length
        if units == "%":
            self.sectors = None
        else:
            self.sectors = (size_units[units] * length) / 512
        self.units = units

    def convert(self, units):
        return (size_units[units] * length) / 512

#class FSType(object):
    #def __init__(self, fs=None,

class Partition(object):
    def __init__(self, disk=None, size=None, type='NORMAL', fs='ext3',
                    name='', start=None, end=None, part=None):
        if part:
            self.__partition = part
            self.__disk = self.__partition.contents.disk
        elif disk and size:
            if not type in partition_type.values():
                raise ValueError("Invalid partition type '%s'" % type)
            part_type = [key for key,val in partition_type.iteritems() if val == type][0]
            if type != 'EXTENDED' and fs != None:
                filesystem = file_system_type_get(fs)
            self.__disk = disk._Disk__disk
            start_sector, end_sector = self._get_sectors(start, end, size)
            self.__partition = partition_new(self.__disk, part_type, filesystem, start_sector, end_sector)
            self.set_name(name)
        else:
            raise Exception("Dude WTF?")

    @property
    def disk(self):
        return Disk(disk=self.__disk)

    @property
    def geom(self):
        start =  self.__partition.contents.geom.start
        end =  self.__partition.contents.geom.end
        length =  self.__partition.contents.geom.length
        return (start, end, length)

    @property
    def num(self):
        return self.__partition.contents.num

    @property
    def type(self):
        return partition_type[self.__partition.contents.type]

    @property
    def fs_type(self):
        try:
            fs = self.__partition.contents.fs_type.contents.name
        except ValueError:
            fs = None
        return fs

    @property
    def name(self):
        return partition_get_name(self.__partition)

    def set_name(self, name):
        if self.disk.type_features != 'PARTITION_NAME':
            raise NotImplementedError("The disk does not support partition names.")
        new_name = partition_set_name(self.__partition, name)
        if not new_name:
            raise Exception("Failed to set name %s to partition." % name)
        return

    def _get_sectors(self, start, end, size):
        if start:
            if not end:
                end = start + size.sectors - 1
            if (end - start) != (size.sectors - 1):
                raise ValueError("Dude, your geometry is messed up.")
        else:
            last_part_num = disk_get_last_partition_num(self.__disk)
            last_part = disk_get_partition(self.__disk, last_part_num)
            last_end_sector = last_part.contents.geom.end
            start = last_end_sector + 1
            end = start + size.sectors - 1
        return (start, end)