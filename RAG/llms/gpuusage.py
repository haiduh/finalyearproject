import psutil
import re

def get_running_game_names():
    """
    Detect potential games running on the system and return only their names.
    Returns a list of game names.
    """
    game_names = []
    game_patterns = [r'\.exe$', r'game', r'play', r'steam', r'origin', r'riot', r'epic']
    game_directories = ['program files\\steam', 'program files (x86)\\steam', 'games', 'epic games']
    
    # Get processes sorted by memory usage
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'exe', 'memory_percent']):
        try:
            info = proc.info
            info['cpu_percent'] = proc.cpu_percent(interval=0.05)
            processes.append(info)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    
    # Sort by memory usage and filter potential games
    for process in sorted(processes, key=lambda x: x['memory_percent'], reverse=True)[:10]:
        name = (process['name'] or "").lower()
        exe_path = (process['exe'] or "").lower()
        
        # Game detection logic
        if process['memory_percent'] > 2.0 and process['cpu_percent'] > 5.0:
            # Check process name patterns
            if any(re.search(pattern, name, re.IGNORECASE) for pattern in game_patterns):
                game_names.append(process['name'])
                continue
            # Check executable path
            if any(directory in exe_path for directory in game_directories):
                game_names.append(process['name'])
                
    print(game_names)
    return game_names
