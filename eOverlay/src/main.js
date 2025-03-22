const { app, BrowserWindow, globalShortcut, ipcMain } = require('electron');

// Global references to prevent garbage collection
let mainWindow;
let devWindow;
let isOverlay = false;

// When Electron has finished initialization
app.whenReady().then(() => {
  createMainWindow();

  // Register a global shortcut for toggling overlay mode (F2)
  globalShortcut.register('F2', () => {
    if (mainWindow) {
      toggleOverlayMode();
    }
  });

  // Register a shortcut to open the Developer Section (F3)
  globalShortcut.register('F3', () => {
    if (devWindow) {
      devWindow.close();  // Close the window if it exists
      devWindow = null;
    } else {
      createDevWindow();  // Create it if it doesn't exist
    }
  });

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createMainWindow();
    }
  });
});

// Handle Electron auto-updates
if (require('electron-squirrel-startup')) {
  app.quit();
}

// Function to apply CORS headers to a window
const applyCORSHeaders = (window) => {
  if (window) {
    window.webContents.session.webRequest.onHeadersReceived((details, callback) => {
      callback({
        responseHeaders: {
          ...details.responseHeaders,
          'Content-Security-Policy': [
            "default-src 'self'; " +
            "connect-src 'self' http://localhost:8000 http://127.0.0.1:8000; " +
            "script-src 'self' 'unsafe-inline' 'unsafe-eval'; " +
            "style-src 'self' 'unsafe-inline'; " +
            "img-src 'self' data: https:; " +
            "font-src 'self' data:;"
          ]
        }
      });
    });
  }
};

// Function to create the main application window
const createMainWindow = () => {
  mainWindow = new BrowserWindow({
    width: 450,
    height: 700,
    frame: false, 
    transparent: true, 
    alwaysOnTop: false, 
    resizable: true, 
    skipTaskbar: false,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
    }
  });

  applyCORSHeaders(mainWindow);

  mainWindow.loadURL(MAIN_WINDOW_WEBPACK_ENTRY);
  // mainWindow.webContents.openDevTools();
};

// Function to create the developer window
const createDevWindow = () => {
  devWindow = new BrowserWindow({
    width: 450,
    height: 600,
    title: "Developer Data Import",
    show: false,
    resizable: true,
    frame: false,
    transparent: true,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
    }
  });

  applyCORSHeaders(devWindow);

  devWindow.loadURL(DEV_WINDOW_WEBPACK_ENTRY);

  devWindow.once('ready-to-show', () => {
    devWindow.show();
  });

  // devWindow.webContents.openDevTools();

  devWindow.on('closed', () => {
    devWindow = null;
  });
};

// Function to toggle the overlay mode
function toggleOverlayMode() {
  if (!mainWindow) return;

  isOverlay = !isOverlay;

  if (isOverlay) {
    mainWindow.show();
    mainWindow.setAlwaysOnTop(true, 'screen-saver');
    mainWindow.setIgnoreMouseEvents(false);
    mainWindow.setResizable(false);
    mainWindow.setSkipTaskbar(true);
    mainWindow.setOpacity(0.8);
    mainWindow.setBackgroundColor('#00000000');
  } else {
    mainWindow.setAlwaysOnTop(false);
    mainWindow.setSkipTaskbar(false);
    mainWindow.minimize();
    mainWindow.setOpacity(1);
  }

  mainWindow.webContents.send('overlay-toggled', isOverlay);
}

// IPC Communication handlers
ipcMain.on('toggle-overlay', () => {
  toggleOverlayMode();
});

ipcMain.on('dev-message', (event, message) => {
  console.log('Received from dev window:', message);
  event.reply('dev-response', `Processed: ${message}`);

  if (mainWindow && mainWindow.webContents) {
    mainWindow.webContents.send('from-dev', message);
  }
});

// Quit when all windows are closed, except on macOS
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

// Clean up when quitting
app.on('will-quit', () => {
  globalShortcut.unregisterAll();
});
