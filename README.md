# Userspace Morpho ILV Driver

ILV protocol implementation in python to communicate with fingerprint readers from userspace using PyUSB

## Supported operations
- [x] Get info
- [x] Get fingerprint
- [ ] Manage local database
- [ ] Local Validation
- [ ] Local identification

## Supported readers
- MSO 300
- MSO CBM

## Installation
### Instal requiered packages:
apt-get install git python python-setuptools python-pil

### Install:
sudo python setup.py install 

### Install udev rules and restart udev
sudo cp 90-morpho.rules /etc/udev/rules.d/
sudo systemctl restart udev

### Test
python testpyMorphoILV.py
> scan

## Usage

-- TODO --

---
Test program with CLI included

### Reference documentation of ILV protocol:
- [MorphoSmart™ Host System Interface specifications](https://www.emssa.net/source/content/Safran/MA500/Morphoaccess%20HSI%20Specification%205.41%20.pdf)
- [MorphoSmart™ Fingerprint scanners Installation Guide](http://www.impro.net/downloads/WebSiteDownloads/documentation/manuals/morpho/Unpublished/installation/MorphoSmart-InstallationGuide.pdf)
