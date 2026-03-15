// Data manager for storing JSON in extension directory (conceptually)
// This creates a data.json representation in extension storage

class ExtensionDataManager {
  constructor() {
    this.dataFile = 'user_behavior_data.json';
  }

  // Save data to extension's persistent storage
  async saveToExtensionFolder() {
    return new Promise((resolve, reject) => {
      chrome.storage.local.get(null, (data) => {
        const exportData = {
          sessionData: data.sessionData || {},
          visitFrequency: data.visitFrequency || {},
          behaviorData: data.behaviorData || {},
          exportTime: new Date().toISOString(),
          lastSaved: new Date().toISOString()
        };
        
        // Store as a "file" in extension storage
        chrome.storage.local.set({
          'extension_data_file': {
            filename: this.dataFile,
            content: JSON.stringify(exportData, null, 2),
            lastModified: Date.now()
          }
        }, () => {
          if (chrome.runtime.lastError) {
            reject(chrome.runtime.lastError);
          } else {
            console.log(`Data saved as ${this.dataFile} in extension storage`);
            resolve(exportData);
          }
        });
      });
    });
  }

  // Read the "file" from extension storage
  async readFromExtensionFolder() {
    return new Promise((resolve, reject) => {
      chrome.storage.local.get(['extension_data_file'], (result) => {
        if (chrome.runtime.lastError) {
          reject(chrome.runtime.lastError);
        } else if (result.extension_data_file) {
          resolve({
            filename: result.extension_data_file.filename,
            content: result.extension_data_file.content,
            data: JSON.parse(result.extension_data_file.content),
            lastModified: new Date(result.extension_data_file.lastModified)
          });
        } else {
          resolve(null);
        }
      });
    });
  }

  // Auto-save data every minute
  startAutoSave() {
    setInterval(() => {
      this.saveToExtensionFolder().catch(console.error);
    }, 60000); // Every minute
  }

  // Export to downloads folder with extension folder reference
  async exportWithReference() {
    const fileData = await this.readFromExtensionFolder();
    if (fileData) {
      const blob = new Blob([fileData.content], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      
      chrome.downloads.download({
        url: url,
        filename: `extension_folder_${fileData.filename}`,
        saveAs: true
      }, () => {
        URL.revokeObjectURL(url); // BUG FIX: revoke blob URL after download to prevent memory leak
      });
      
      return fileData;
    }
    return null;
  }
}

// Initialize data manager
const dataManager = new ExtensionDataManager();

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
  module.exports = ExtensionDataManager;
}