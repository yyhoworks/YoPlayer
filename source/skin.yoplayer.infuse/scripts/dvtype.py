import xbmc
import json
import sys
import os

def log(msg):
    """Helper function to log messages to Kodi log"""
    xbmc.log(f"[dvtype.py] {msg}", level=xbmc.LOGINFO)

def get_info_label(label):
    """Get the value of a Kodi InfoLabel"""
    try:
        value = xbmc.getInfoLabel(label)
        return value
    except Exception as e:
        log(f"Error getting InfoLabel {label}: {e}")
        return ""

def execute_json_rpc(method, params=None):
    """Execute a JSON-RPC request and return the parsed result object"""
    request = {
        "jsonrpc": "2.0",
        "method": method,
        "id": 1
    }
    if params:
        request["params"] = params
    
    json_string = json.dumps(request)
    response_string = xbmc.executeJSONRPC(json_string)
    
    try:
        response = json.loads(response_string)
        if 'error' in response:
            log(f"RPC Error for {method}: {response['error']}")
            return None
        
        if 'result' in response:
            return response['result']
        else:
            log(f"No result field in RPC response for {method}: {response}")
            return None
    except Exception as e:
        log(f"Failed to parse JSON RPC response: {e}")
        return None

def set_skin_string(name, value):
    """Set a skin string variable using Skin.SetString builtin"""
    command = f'Skin.SetString({name},{value})'
    xbmc.executebuiltin(command)
    log(f"Executed builtin: {command}")

def get_setting_value(setting_id):
    """Get the value of a specific setting via JSON-RPC"""
    rpc_params = {
        "setting": setting_id
    }
    
    result = execute_json_rpc("Settings.GetSettingValue", rpc_params)
    
    if result is not None and isinstance(result, dict) and 'value' in result:
        return result['value']
        
    return None

def read_file_content(filepath):
    """Read content from a system file safely"""
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r') as f:
                return f.read()
        else:
            log(f"File does not exist: {filepath}")
            return None
    except Exception as e:
        log(f"Error reading file {filepath}: {e}")
        return None

def main():
    # Check arguments
    args = sys.argv[1:]
    if not args or "detect" not in args:
        log("Script run without 'detect' parameter. Exiting.")
        return

    log("Starting Dolby Vision Type detection...")

    # 1. Get System.SupportedHDRTypes using InfoLabel
    supported_hdr_types = get_info_label("System.SupportedHDRTypes")
    
    log(f"System.SupportedHDRTypes (InfoLabel): '{supported_hdr_types}'")

    # Normalize for case-insensitive comparison
    hdr_types_lower = supported_hdr_types.lower()
    
    cpmdvmode_val = ""
    hidehdr_val = ""
    
    # Define mappings
    map_dv = {
        0: "DV-std",
        1: "DV-LL",
        2: "HDR-444",
        3: "VS10 Only",
        4: "HDR-422"
    }
    
    map_hdr = {
        0: "PL-HDR",
        1: "PL-HDR",
        2: "HDR-444",
        3: "VS10 Only",
        4: "HDR-422"
    }

    dv_type_setting_id = "coreelec.amlogic.dolbyvision.type"
    vsvdb_setting_id = "coreelec.amlogic.dolbyvision.vsvdb.inject"

    # Determine Case
    if "vision" in hdr_types_lower:
        # Case 1: Contains "Vision"
        log("Case 1: Vision detected")
        current_type = get_setting_value(dv_type_setting_id)
        log(f"Current DV Type setting: {current_type}")
        
        try:
            type_int = int(current_type)
            if type_int in map_dv:
                cpmdvmode_val = map_dv[type_int]
            else:
                log(f"Unknown DV type value: {type_int}, defaulting to VS10 Only")
                cpmdvmode_val = "VS10 Only"
        except (ValueError, TypeError):
            log(f"Invalid DV type value: {current_type}, defaulting to VS10 Only")
            cpmdvmode_val = "VS10 Only"
            
    elif "hdr" in hdr_types_lower:
        # Case 2: Contains "HDR" but not "Vision"
        log("Case 2: HDR detected (no Vision)")
        current_type = get_setting_value(dv_type_setting_id)
        log(f"Current DV Type setting: {current_type}")
        
        try:
            type_int = int(current_type)
            if type_int in map_hdr:
                cpmdvmode_val = map_hdr[type_int]
            else:
                log(f"Unknown HDR type value: {type_int}, defaulting to VS10 Only")
                cpmdvmode_val = "VS10 Only"
        except (ValueError, TypeError):
            log(f"Invalid HDR type value: {current_type}, defaulting to VS10 Only")
            cpmdvmode_val = "VS10 Only"
            
    else:
        # Case 3: Empty or neither Vision nor HDR
        log("Case 3: No Vision or HDR detected in InfoLabel. Checking sysfs...")
        
        hdr_cap_path = "/sys/devices/virtual/amhdmitx/amhdmitx0/hdr_cap"
        hdr_cap_content = read_file_content(hdr_cap_path)
        
        has_active_hdr = False
        
        if hdr_cap_content:
            log(f"Read hdr_cap content:\n{hdr_cap_content}")
            
            # Define keys to look for
            keys_to_check = [
                "SMPTE ST 2084",
                "Hybrid Log-Gamma",
                "Supported SMD type1"
            ]
            
            for key in keys_to_check:
                # Look for pattern "Key: Value"
                # We split lines to be safer, though regex could also work
                for line in hdr_cap_content.splitlines():
                    if key in line:
                        # Extract value after colon
                        parts = line.split(':')
                        if len(parts) > 1:
                            val_str = parts[-1].strip()
                            if val_str == "1":
                                log(f"Found active HDR capability: {key} = 1")
                                has_active_hdr = True
                                break # Found one, no need to check further for this key
                if has_active_hdr:
                    break # Found at least one active capability
        else:
            log("Could not read hdr_cap file or file is empty.")

        if has_active_hdr:
            log("At least one HDR capability is active (1). Setting PL-HDR.")
            cpmdvmode_val = "PL-HDR"
            hidehdr_val = "1"
        else:
            log("No active HDR capabilities found or file missing. Setting VS10 Only.")
            cpmdvmode_val = "VS10 Only"
            hidehdr_val = "0"

    # Common Step: Read vsvdb.inject for all cases
    vsvdb_value = get_setting_value(vsvdb_setting_id)
    log(f"VSVDB Inject setting: {vsvdb_value}")
    
    if isinstance(vsvdb_value, bool):
        cpmvsvdb_val = "ON" if vsvdb_value else "OFF"
    elif isinstance(vsvdb_value, str):
        cpmvsvdb_val = "ON" if vsvdb_value.lower() == "true" else "OFF"
    else:
        cpmvsvdb_val = "OFF"
        log(f"Unknown VSVDB value type: {type(vsvdb_value)}, defaulting to OFF")

    # Apply Skin Strings using the new helper
    if cpmdvmode_val:
        set_skin_string("cpmdvmode", cpmdvmode_val)
    
    if hidehdr_val:
        set_skin_string("hidehdr", hidehdr_val)
        
    set_skin_string("cpmvsvdb", cpmvsvdb_val)

    log("Detection script finished.")

if __name__ == "__main__":
    main()