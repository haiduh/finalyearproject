import { app, BrowserWindow, ipcMain } from 'electron';
import * as path from 'path';
import * as url from 'url';

let mainWindow: BrowserWindow | null = null;

function createWindow() {
    mainWindow = new BrowserWindow({
      width: 800,
      height: 600,
      webPreferences: {
        nodeIntegration: false,
        contextIsolation: true,
        preload: path.join(__dirname, '../preload/preload.js')
      },
      transparent: true,
      frame: false,
      alwaysOnTop: true
    });
  
    if (process.env.NODE_ENV === 'development') {
      mainWindow.loadURL('http://localhost:4000');
      mainWindow.webContents.openDevTools();
    } else {
      const indexFilePath = path.join(__dirname, '../dist/renderer/index.html');
      console.log('Loading index file from: ', indexFilePath);
  
      mainWindow.loadFile(indexFilePath);
    }
  
    mainWindow.setIgnoreMouseEvents(false);
  
    mainWindow.on('closed', () => {
      mainWindow = null;
    });
  }  

app.whenReady().then(createWindow);

app.on('window-all-closed', () => {
  if (process.platform !== 'darwin') {
    app.quit();
  }
});

app.on('activate', () => {
  if (BrowserWindow.getAllWindows().length === 0) {
    createWindow();
  }
});

ipcMain.on('toggle-click-through', (_, passthrough) => {
  if (mainWindow) {
    mainWindow.setIgnoreMouseEvents(passthrough);
  }
});
