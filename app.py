"""Desktop entry point. The portable Windows package uses its bundled runtime."""
import os
from pathlib import Path
BASE=Path(__file__).resolve().parent
if os.name=='nt':
    runtime=BASE/'runtime'
    if (runtime/'DLLs').is_dir():
        _dll_directory=os.add_dll_directory(str(runtime/'DLLs'))
    if (runtime/'tcl/tcl8.6').is_dir():
        os.environ['TCL_LIBRARY']=str(runtime/'tcl/tcl8.6')
        os.environ['TK_LIBRARY']=str(runtime/'tcl/tk8.6')
try:
    from lotfsync.gui import main
    main()
except Exception:
    import traceback
    text=traceback.format_exc()
    log=Path.home()/'LOTF_Save_Sync_startup_error.txt'
    try:log.write_text(text,encoding='utf-8')
    except OSError:pass
    if os.name=='nt':
        import ctypes
        ctypes.windll.user32.MessageBoxW(None,'Avvio non riuscito / Startup failed.\n\n'+str(log)+'\n\n'+text,'LOTF Save Sync',16)
    else:raise
