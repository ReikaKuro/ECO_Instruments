## ECO_Instruments
Tool for turning off automatically Signal Analyzers and Signal Generators (R&S and Keysight) that are mapped in <b>Setups.json</b>
via SCPI port.

## Important!!
Turn on AC Power Loss in bios. This way after powering up device again via PDU, it will turn on automatically.
In other case after powering up device won't start automatically, and you will need to turn it on manually.

### Compatible instruments
Works for R&S FSV, SMW, SMBV and Keysight
- Rohde & Schwarz: FSV, SMW, SMBV (Might work for other models as well if their shutdown command = SYSTem:SHUTdown)
- Keysight (Should work for all models as long as their shutdown command = :SYSTem:PDOWn)
- GUDE PDU

### How it works
- Instruments are mapped to PCs which might user it and PDU of GUDE.
- Instruments are only in use if someone is occupying one of setups that is linked to it
- Script monitors setups from 22:00 to 6:00 every 10 minutes
- If someone is occupying one of setups, script will skip all further actions regarding this set of instruments and will start checking next one
- If setup between 22:00 and 6:00 setup is not occupied for more than hour, starts procedure of turning off device completely as safe as possible
- Device is turned off firstly, if communication with device stops in 30 seconds, script will wait (can be changed by <b>chaning wait_before_turn_off_pdu</b> 
 value) 5 minutes to let the device end all the process and shutdown completely. After that time, power on the PDU will be cut off

## Requirements:

    1.  Python version: 3.7.9, venv environment
    
    2.  Install all requirements using:
        python -m pip install --upgrade -r requirements.txt
    
    3.  Install tad.pfu using:
        # TODO write new package for controlling GUDE PDUs

## Example Setups.json

Respect this order:

    |Setups
        |setup1
            |instruments
                |pdu
                |sa
                    |ip
                    |port
                    |type
                    |scpi_port
                |sg
                    |ip
                    |port
                    |type
                    |scpi_port
            |PCs
                |ip
                |login
                |password
        |setup2
            |instruments
                |pdu
                |sa
                    |ip
                    |port
                    |type
                    |scpi_port
                |sg
                    |ip
                    |port
                    |type
                    |scpi_port
            |PCs
                |ip
                |login
                |password
    etc.

_

        {
	"setups": {
		"setup1": {
			"instruments": {
				"pdu": "255.255.255.255", <-- pdu to which instruments are connected
				"SA": {
					"ip": "255.255.255.255", <-- instrument ip
					"port": "1", <-- port to which instrument is connected
					"type": "RS", <-- R&S, or KS if Keysight
					"scpi_port" : "1111" <-- scpi_port on instrument through which shutdown command can be executed
				},
				"SG": {
					"ip": "255.255.255.255",
					"port": "2",
					"type": "RS",
					"scpi_port" : "1111"
				}
			},
			"PCs": {
				"PC1": {
					"ip": "255.255.255.255",
					"login": "pc_username",
					"password": "pc_password"
				}
			}
		},
		"setup2": {
			"instruments": {
				"pdu": "255.255.255.255",
				"SA": {
					"ip": "255.255.255.255",
					"port": "6",
					"type": "RS",
					"scpi_port" : "1111"
				},
				"SG": {
					"ip": "255.255.255.255",
					"port": "7",
					"type": "KS",
					"scpi_port" : "1111"
				}
			},
			"PCs": {        <---- multiple PCs validation
				"PC1": {
					"ip": "255.255.255.255",
					"login": "pc_username",
					"password": "pc_password"
				},
				"PC2": {
					"ip": "255.255.255.255",
					"login": "pc_username",
					"password": "pc_password"
				}
			}
		}
	}
}