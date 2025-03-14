// Prevents additional console window on Windows in release, DO NOT REMOVE!!
#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]

use std::process::Command;
use tauri::Manager;

#[tauri::command]
fn start_rag_api() -> Result<(), String> {
    std::thread::spawn(|| {
        let output = Command::new("")
            .output()
            .expect("Failed to start RAG API");
        println!("RAG API exited: {:?}", output);
    });
    Ok(())
}

fn main() {
    tauri::Builder::default()
        .setup(|app| {
            // Start the RAG API when the app starts
            start_rag_api().unwrap();
            Ok(())
        })
        .invoke_handler(tauri::generate_handler![start_rag_api])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}