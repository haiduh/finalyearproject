import { contextBridge, ipcRenderer } from 'electron';

// Expose protected methods that allow the renderer process to use
// the ipcRenderer without exposing the entire object
contextBridge.exposeInMainWorld(
  'electron',
  {
    toggleClickThrough: (passthrough: boolean) => {
      ipcRenderer.send('toggle-click-through', passthrough);
    },
    // You can add more methods here for overlay functionality
  }
);