const { app, BrowserWindow, globalShortcut, ipcMain} = require('electron');

let mainWindow;
let isOverlay = false;

app.whenReady().then(() => {
  createWindow();

  // Register a global shortcut for toggling overlay mode
  globalShortcut.register('F2', () => {
    if (mainWindow) {
      toggleOverlayMode();
    }
  });

  app.on('activate', () => {
    if (BrowserWindow.getAllWindows().length === 0) {
      createWindow();
    }
  });
});

// Handle creating/removing shortcuts on Windows when installing/uninstalling.
if (require('electron-squirrel-startup')) {
  app.quit();
}

const createWindow = () => {
  mainWindow = new BrowserWindow({
    width: 450,
    height: 600,
    frame: false, // Frameless window for clean overlay appearance
    transparent: true, // Allows for rounded corners and transparency
    alwaysOnTop: false, // Keeps the overlay above the game
    resizable: true, // Allow users to resize if needed
    skipTaskbar: false,
    webPreferences: {
      nodeIntegration: true,
      contextIsolation: false,
    }
  });

  // Set Content Security Policy
  mainWindow.webContents.session.webRequest.onHeadersReceived((details, callback) => {
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

  // Load the UI
  mainWindow.loadURL(MAIN_WINDOW_WEBPACK_ENTRY); // Change to your frontend entry point

  // Open DevTools for debugging (remove in production)
  mainWindow.webContents.openDevTools();
};

function toggleOverlayMode() {
  if (!mainWindow) return;

  isOverlay = !isOverlay; // Toggle overlay state

  if (isOverlay) {
    // Enable overlay mode
    mainWindow.show(); // Ensure window is visible
    mainWindow.setAlwaysOnTop(true, 'screen-saver');
    mainWindow.setIgnoreMouseEvents(false);
    mainWindow.setResizable(false);
    mainWindow.setSkipTaskbar(true);
    mainWindow.setOpacity(0.8); // Slight transparency
    mainWindow.setBackgroundColor('#00000000'); // Fully transparent
  } else {
    // Exit overlay mode and hide the window
    mainWindow.setAlwaysOnTop(false);
    mainWindow.setSkipTaskbar(false);
    mainWindow.minimize(); // Minimizes instead of closing
    mainWindow.setOpacity(1);
  }

  // Send the updated overlay state to renderer
  mainWindow.webContents.send('overlay-toggled', isOverlay);
}

// Listen for IPC event to toggle overlay mode
ipcMain.on('toggle-overlay', () => {
  toggleOverlayMode();
});

// Quit when all windows are closed, except on macOS.
app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});
