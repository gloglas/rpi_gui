apt-get update || exit 1
apt-get install -y python3-pil python3-pip python3-numpy python3-serial python3-setuptools python3-pyudev python3-dev python3-smbus python3-rpi.gpio python3-netifaces
pip3 install spidev keyboard
echo "Setting up interfaces"
echo 'dtparam=i2c_arm=on' >> /boot/config.txt
echo 'dtparam=i2c1=on' >> /boot/config.txt
echo 'dtparam=spi=on' >> /boot/config.txt
echo 'i2c-bcm2708' >> /etc/modules
echo 'i2c-dev' >> /etc/modules

echo -e "\nInstalling munifying\n"
git clone https://github.com/RoganDawes/munifying
cd munifying
./install_libusb.sh
go build || echo -e "\nMunifying Failed!!!\n"

echo -e "\nSetting up startup scripts\n"
# install vlasti gui script a path
echo 'nice -n -5 python3 /root/rpi_gui/main.py &' >> /usr/local/P4wnP1/scripts/startup.sh
echo 'sleep 10' >> /usr/local/P4wnP1/scripts/startup.sh
echo 'service getty@tty1.service stop # Disable tty1 for AnalyzeHID function' >> /usr/local/P4wnP1/scripts/startup.sh

systemctl mask ctrl-alt-del.target
systemctl daemon-reload

mkdir rpi_gui/log
mkdir rpi_gui/ducky

echo -e "\nNow you need to reboot!"