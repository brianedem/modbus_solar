from sEdge import sEdge, point

#system = sEdge('solaredgeinv.local', 1502)
#system = sEdge('192.168.1.67', 1502)
system = sEdge('192.168.12.186', 1502)
ei_battery          = point(system, "Export", "DERStorageCapacity", "SoC")

system.refresh_readings()

battery_soc = ei_battery.read_point()
print(f"Battery state of charge = {battery_soc[0]:6.2f} {battery_soc[1]}")
