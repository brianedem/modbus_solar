# modbus_solar
The SolarEdge inverters expose system data via modbusTCP.
The format of the data is specified in the SunSpec Models, which this software directly uses the json form.

Part 1 of the project is to discover the model types used by the SolarEdge inverter and build a map to locate the various "points" using the model data.
Part 2 will develop various applications and services that will use the results of part 1, such as
  - CLI battery status
  - Periodic logging of system status to a database for historical information
  - Web server of current system state
