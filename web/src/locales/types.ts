export interface Translations {
  common: {
    close: string;
    cancel: string;
    apply: string;
    confirm: string;
    loading: string;
    auto: string;
    singleChoice: string;
    multipleChoice: string;
    step: string;
    of: string;
    activeFlags: string;
    destination: string;
    dataFolder: string;
    notSet: string;
    clickToSimulate: string;
    filesDetected: string;
  };
  header: {
    title: string;
    closeMod: string;
    closeModTooltip: string;
    waitingArchive: string;
  };
  sidebar: {
    openFomod: string;
    openFomodTooltip: string;
    modInfo: string;
    chooseDataDir: string;
    chooseStagingDir: string;
    generateStaging: string;
  };
  welcome: {
    title: string;
    subtitle: string;
    dropTitle: string;
    supportedFormats: string;
    orFolder: string;
    loadArchiveBtn: string;
    loadFolderBtn: string;
    loadDemoBtn: string;
    standaloneEngine: string;
    noGameRequired: string;
    selectLanguage: string;
  };
  steps: {
    noStepsFound: string;
    loadDemoAction: string;
    prevStep: string;
    nextStep: string;
    finishStep: string;
    autoDetected: string;
  };
  preview: {
    instructionsTitle: string;
    clickToEnlarge: string;
    enlarge: string;
    defaultTitle: string;
    defaultSubtitle: string;
  };
  loading: {
    title: string;
    inProgress: string;
    sub: string;
  };
  error: {
    cannotLoad: string;
    tipsTitle: string;
    tip1: string;
    tip2: string;
  };
  stagingWarning: {
    title: string;
    message: string;
    choose: string;
    cancel: string;
  };
  modals: {
    openMod: {
      title: string;
      fromComputer: string;
      browseArchive: string;
      fullSupport: string;
      browseArchiveDesc: string;
      browseFolder: string;
      localFolder: string;
      browseFolderDesc: string;
      demoMods: string;
      load: string;
      cbbeDesc: string;
      smimDesc: string;
    };
    dataDir: {
      title: string;
      desc: string;
      currentPath: string;
      browseFolder: string;
      detectedPlugins: string;
      loadPresets: string;
      manualInput: string;
      apply: string;
      noFolderSelected: string;
      presetBaseName: string;
      presetBaseDesc: string;
      presetEssentialName: string;
      presetEssentialDesc: string;
      presetPhysicsName: string;
      presetPhysicsDesc: string;
    };
    modInfo: {
      title: string;
      name: string;
      author: string;
      version: string;
      website: string;
      description: string;
    };
    staging: {
      title: string;
      filesInstalled: string;
      stagingLog: string;
      downloadZip: string;
      writeLocal: string;
      cleanInstall: string;
      totalFiles: string;
      totalSize: string;
      browserNotSupported: string;
      zipError: string;
      writeSuccess: string;
    };
    folderSelect: {
      title: string;
      desktop: string;
      downloads: string;
      customManual: string;
      nativeFolder: string;
      close: string;
    };
    imagePreview: {
      title: string;
      close: string;
    };
  };
}

export type Language = 'fr' | 'en' | 'it' | 'es';

export interface LanguageInfo {
  code: Language;
  name: string;
  nativeName: string;
  flag: string;
}
