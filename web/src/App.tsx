import React, { useState, useEffect, useRef } from 'react';
import {
  FomodStep,
  FomodGroup,
  FomodOption,
  FomodMetadata,
  ArchiveIndex,
  VirtualFileEntry,
  StagingResult,
  FomodFileItem,
  FomodFolderItem,
  ConditionalInstallPattern,
} from './types/fomod';
import {
  parseModuleConfigXml,
  parseInfoXml,
  norm,
  findFileInIndex,
  isOptionRecommended,
} from './utils/fomodParser';
import { extractAnyArchive, reanchorIndex, selectFomodXml } from './utils/archiveExtractor';
import {
  buildStaging,
  writeStagingToLocalDirectoryHandle,
} from './utils/fomodStaging';
import {
  SAMPLE_MOD_CBBE,
  SAMPLE_MOD_SMIM,
  buildSampleArchiveIndex,
  SampleMod,
  createSvgPlaceholder,
} from './data/sampleMods';
import ModInfoModal from './components/ModInfoModal';
import ImagePreviewModal from './components/ImagePreviewModal';
import DataDirModal from './components/DataDirModal';
import StagingResultModal from './components/StagingResultModal';
import OpenModModal from './components/OpenModModal';
import FolderSelectModal from './components/FolderSelectModal';
import LanguageSelector from './components/LanguageSelector';
import { useI18n } from './locales';

export default function App() {
  const { strings } = useI18n();

  // --- STATE ---
  const [modName, setModName] = useState<string>('Caliente\'s Beautiful Bodies Enhancer - CBBE - SE');
  const [steps, setSteps] = useState<FomodStep[]>([]);
  const [currentStepIdx, setCurrentStepIdx] = useState<number>(0);
  const [moduleHeaderImage, setModuleHeaderImage] = useState<string | undefined>();
  const [metadata, setMetadata] = useState<FomodMetadata>({
    name: '',
    author: '',
    version: '',
    website: '',
    description: '',
  });
  const [archiveIndex, setArchiveIndex] = useState<ArchiveIndex>({
    files: new Map(),
    dirs: new Map(),
  });
  const [requiredFiles, setRequiredFiles] = useState<(FomodFileItem | FomodFolderItem)[]>([]);
  const [conditionalFileInstalls, setConditionalFileInstalls] = useState<ConditionalInstallPattern[]>([]);

  // Selections state: map of stepId -> record of groupId -> single string or array of strings
  const [selections, setSelections] = useState<
    Record<string, Record<string, string | string[]>>
  >({});

  // Active flags collected from selected options
  const [activeFlags, setActiveFlags] = useState<Record<string, string>>({});

  // Preview state (Right column)
  const [previewDesc, setPreviewDesc] = useState<string>('Description');
  const [previewImgUrl, setPreviewImgUrl] = useState<string | null>(null);
  const [, setCurrentHoveredOption] = useState<FomodOption | null>(null);
  const [fullPreviewModalOpen, setFullPreviewModalOpen] = useState<boolean>(false);

  // Data dir
  const [dataDirPath, setDataDirPath] = useState<string | null>(null);
  const [installedBasenames, setInstalledBasenames] = useState<Set<string>>(new Set());
  const [dataModalOpen, setDataModalOpen] = useState<boolean>(false);

  // Staging
  const [stagingDirPath, setStagingDirPath] = useState<string>('Bureau (Desktop)');
  const [stagingDirectoryHandle, setStagingDirectoryHandle] = useState<FileSystemDirectoryHandle | null>(null);
  const [stagingResult, setStagingResult] = useState<StagingResult | null>(null);
  const [directWriteSuccess, setDirectWriteSuccess] = useState<boolean>(false);
  const [stagingModalOpen, setStagingModalOpen] = useState<boolean>(false);
  const [folderSelectModalOpen, setFolderSelectModalOpen] = useState<boolean>(false);

  // Mod info modal & open mod modal
  const [infoModalOpen, setInfoModalOpen] = useState<boolean>(false);
  const [openModModalOpen, setOpenModModalOpen] = useState<boolean>(false);

  // Loading & Drag-drop
  const [isLoading, setIsLoading] = useState<boolean>(false);
  const [isDragOver, setIsDragOver] = useState<boolean>(false);
  const [statusMessage, setStatusMessage] = useState<string>('');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const dragCounterRef = useRef<number>(0);

  // Column resizing state (reduced 1st column by 1/4: 26% -> 19.5%, distributed to other columns)
  const [colWidths, setColWidths] = useState<[number, number, number]>([19.5, 32.5, 48]);
  const containerRef = useRef<HTMLDivElement>(null);
  const draggingSashRef = useRef<number | null>(null);

  // Hidden inputs
  const archiveInputRef = useRef<HTMLInputElement>(null);
  const folderInputRef = useRef<HTMLInputElement>(null);

  // Empêcher le navigateur d'ouvrir/télécharger le fichier si lâché hors zone
  useEffect(() => {
    const preventDefaults = (e: DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
    };
    window.addEventListener('dragover', preventDefaults);
    window.addEventListener('drop', preventDefaults);
    return () => {
      window.removeEventListener('dragover', preventDefaults);
      window.removeEventListener('drop', preventDefaults);
    };
  }, []);

  // --- FERMER LE MOD (RETOUR À L'ÉCRAN D'ACCUEIL) ---
  const handleCloseMod = () => {
    setSteps([]);
    setModName('');
    setRequiredFiles([]);
    setSelections({});
    setActiveFlags({});
    setCurrentStepIdx(0);
    setPreviewImgUrl(null);
    setPreviewDesc('Description');
    setArchiveIndex({ files: new Map(), dirs: new Map() });
    setStagingResult(null);
  };

  // --- GESTION CENTRALE DE L'APERÇU IMAGE & DESCRIPTION ---
  const updateOptionPreview = (
    opt: FomodOption | null,
    step: FomodStep | null = null,
    group: FomodGroup | null = null,
    index: ArchiveIndex | null = archiveIndex,
    modHeaderImg: string | undefined = moduleHeaderImage
  ) => {
    if (!opt) {
      setPreviewDesc('Sélectionnez ou survolez une option pour afficher ses instructions et sa description.');
      setPreviewImgUrl(createSvgPlaceholder('Aperçu FOMOD', 'Option de configuration du mod', '#1e293b', '#38bdf8'));
      setCurrentHoveredOption(null);
      return;
    }

    setCurrentHoveredOption(opt);
    setPreviewDesc(opt.description || '(aucune description)');

    let resolvedUrl: string | null = null;

    // 1. Chercher l'image spécifiée sur l'option
    if (opt.imagePath && index) {
      const entry = findFileInIndex(index, opt.imagePath);
      if (entry) {
        if (!entry.url && entry.blob) {
          try { entry.url = URL.createObjectURL(entry.blob); } catch {}
        }
        if (entry.url) resolvedUrl = entry.url;
      }
    }

    // 2. Si non trouvée, chercher dans l'archive indexée si un fichier image correspond au nom de l'option
    if (!resolvedUrl && opt.name && index) {
      const entry = findFileInIndex(index, opt.name);
      if (entry && entry.path.toLowerCase().match(/\.(jpe?g|png|bmp|webp|svg)$/i)) {
        if (!entry.url && entry.blob) {
          try { entry.url = URL.createObjectURL(entry.blob); } catch {}
        }
        if (entry.url) resolvedUrl = entry.url;
      }
    }

    // 3. Fallback sur l'image d'en-tête du groupe, de l'étape ou du module si l'option n'en possède pas
    if (!resolvedUrl && group?.headerImage && index) {
      const entry = findFileInIndex(index, group.headerImage);
      if (entry?.url) resolvedUrl = entry.url;
    }
    if (!resolvedUrl && step?.headerImage && index) {
      const entry = findFileInIndex(index, step.headerImage);
      if (entry?.url) resolvedUrl = entry.url;
    }
    if (!resolvedUrl && modHeaderImg && index) {
      const entry = findFileInIndex(index, modHeaderImg);
      if (entry?.url) resolvedUrl = entry.url;
    }

    // 4. Si aucune image réelle n'est trouvée dans le FOMOD, RESTAURER LE PLACEHOLDER GRAPHIQUE SVG ÉLÉGANT
    if (!resolvedUrl) {
      const shortDesc = opt.description
        ? (opt.description.split('.')[0] + '.').slice(0, 65)
        : 'Option de configuration du mod';
      resolvedUrl = createSvgPlaceholder(opt.name, shortDesc, '#1e293b', '#38bdf8');
    }

    setPreviewImgUrl(resolvedUrl);
  };

  const handleHoverOption = (opt: FomodOption) => {
    const curStep = steps[currentStepIdx];
    const curGrp = curStep?.groups.find(g => g.options.some(o => o.id === opt.id));
    updateOptionPreview(opt, curStep, curGrp, archiveIndex, moduleHeaderImage);
  };

  // Synchroniser l'aperçu lors du changement d'étape
  useEffect(() => {
    if (steps.length > 0 && steps[currentStepIdx]) {
      const curStep = steps[currentStepIdx];
      const curGrp = curStep.groups[0];
      const firstOpt = curGrp?.options[0];
      if (firstOpt) {
        updateOptionPreview(firstOpt, curStep, curGrp, archiveIndex, moduleHeaderImage);
      }
    }
  }, [currentStepIdx]);

  // --- CHARGEMENT MOD DÉMO ---
  const loadSampleMod = (sample: SampleMod) => {
    try {
      setIsLoading(true);
      const parsedConfig = parseModuleConfigXml(sample.moduleConfigXml);
      const parsedInfo = parseInfoXml(sample.infoXml);
      const index = buildSampleArchiveIndex(sample);

      setModName(parsedConfig.moduleName || sample.name);
      setSteps(parsedConfig.steps);
      setRequiredFiles(parsedConfig.requiredInstallFiles);
      setConditionalFileInstalls(parsedConfig.conditionalFileInstalls || []);
      setMetadata(parsedInfo);
      setArchiveIndex(index);
      setCurrentStepIdx(0);
      setModuleHeaderImage(parsedConfig.moduleHeaderImage);

      initSelections(parsedConfig.steps, index, installedBasenames, false);

      const firstOpt = parsedConfig.steps[0]?.groups[0]?.options[0];
      const firstGrp = parsedConfig.steps[0]?.groups[0];
      const firstStep = parsedConfig.steps[0];
      if (firstOpt) {
        updateOptionPreview(firstOpt, firstStep, firstGrp, index, parsedConfig.moduleHeaderImage);
      } else {
        updateOptionPreview(null, null, null, index, parsedConfig.moduleHeaderImage);
      }
    } catch (e) {
      console.error('Erreur chargement mod de démonstration:', e);
    } finally {
      setIsLoading(false);
    }
  };

  // --- INITIALISATION PRÉ-SÉLECTIONS ---
  const initSelections = (
    stepList: FomodStep[],
    index: ArchiveIndex,
    installed: Set<string>,
    preserveManual: boolean = false
  ) => {
    const initial: Record<string, Record<string, string | string[]>> = preserveManual ? { ...selections } : {};
    const flags: Record<string, string> = preserveManual ? { ...activeFlags } : {};

    stepList.forEach((step) => {
      if (!initial[step.id]) initial[step.id] = {};
      step.groups.forEach((grp) => {
        const isSingle = grp.type === 'SelectExactlyOne' || grp.type === 'SelectAtMostOne';
        if (isSingle) {
          let chosen: FomodOption | undefined;
          for (const opt of grp.options) {
            if (isOptionRecommended(opt, installed, flags)) {
              chosen = opt;
              break;
            }
          }
          if (!chosen) {
            for (const opt of grp.options) {
              const rec = typeof opt.typeDescriptor === 'string' ? opt.typeDescriptor.toLowerCase() : '';
              if (rec === 'recommended') {
                chosen = opt;
                break;
              }
            }
          }
          if (!chosen && grp.type === 'SelectExactlyOne' && grp.options.length > 0) {
            chosen = grp.options[0];
          }

          if (chosen) {
            if (!preserveManual || !initial[step.id][grp.id] || initial[step.id][grp.id] === '__none__') {
              initial[step.id][grp.id] = chosen.name;
              Object.assign(flags, chosen.flags);
            }
          } else if (!preserveManual) {
            initial[step.id][grp.id] = '__none__';
          }
        } else {
          const currentSelected = new Set<string>(
            preserveManual && Array.isArray(initial[step.id][grp.id])
              ? (initial[step.id][grp.id] as string[])
              : []
          );
          grp.options.forEach((opt) => {
            if (isOptionRecommended(opt, installed, flags)) {
              currentSelected.add(opt.name);
              Object.assign(flags, opt.flags);
            }
          });
          initial[step.id][grp.id] = Array.from(currentSelected);
        }
      });
    });

    setSelections(initial);
    setActiveFlags(flags);
  };

  // --- TRAITEMENT DOSSIER LOCAL / DÉCOMPRESSÉ ---
  const handleFolderFiles = async (fileList: FileList | File[]) => {
    setIsLoading(true);
    setErrorMessage(null);
    setStatusMessage('Indexation du dossier local...');
    try {
      const filesMap = new Map<string, VirtualFileEntry>();
      const dirsMap = new Map<string, string>();

      const filesArray = Array.from(fileList);
      if (filesArray.length === 0) {
        setIsLoading(false);
        return;
      }

      for (const file of filesArray) {
        const rawPath = norm((file as any).webkitRelativePath || file.name);
        if (rawPath.includes('__MACOSX/') || rawPath.endsWith('/.DS_Store') || rawPath === '.DS_Store') continue;

        const normalized = norm(rawPath);
        const lower = normalized.toLowerCase();

        let url: string | undefined;
        const ext = lower.split('.').pop() || '';
        if (['png', 'jpg', 'jpeg', 'bmp', 'webp', 'svg'].includes(ext)) {
          try {
            url = URL.createObjectURL(file);
          } catch (e) {
            console.warn(e);
          }
        }

        filesMap.set(lower, {
          path: normalized,
          isDir: false,
          size: file.size,
          blob: file,
          url,
        });

        const parts = normalized.split('/');
        let cur = '';
        for (let i = 0; i < parts.length - 1; i++) {
          cur = cur ? `${cur}/${parts[i]}` : parts[i];
          dirsMap.set(cur.toLowerCase(), cur);
        }
      }

      // Re-ancrer l'index à la racine du FOMOD (supprime tout dossier racine parent englobant)
      const reanchored = reanchorIndex(filesMap, dirsMap);

      const { moduleConfigXml: moduleConfigText, infoXml: infoText } = await selectFomodXml(reanchored.files);

      if (!moduleConfigText) {
        setErrorMessage(
          'Impossible de trouver le fichier "fomod/ModuleConfig.xml" dans ce dossier !\n\n' +
          'Assurez-vous que le dossier déposé contient bien le sous-répertoire "fomod" avec son fichier "ModuleConfig.xml".'
        );
        setIsLoading(false);
        return;
      }


      setStatusMessage('Analyse de la configuration FOMOD...');
      const parsedConfig = parseModuleConfigXml(moduleConfigText);
      const parsedInfo = infoText
        ? parseInfoXml(infoText)
        : {
            name: parsedConfig.moduleName || 'Mod FOMOD',
            author: 'Inconnu',
            version: '1.0',
            website: '',
            description: 'Dossier de mod local',
          };

      const newIndex: ArchiveIndex = reanchored;

      setModName(parsedConfig.moduleName || 'Mod FOMOD');
      setSteps(parsedConfig.steps);
      setRequiredFiles(parsedConfig.requiredInstallFiles);
      setConditionalFileInstalls(parsedConfig.conditionalFileInstalls || []);
      setMetadata(parsedInfo);
      setArchiveIndex(newIndex);
      setCurrentStepIdx(0);
      setModuleHeaderImage(parsedConfig.moduleHeaderImage);

      initSelections(parsedConfig.steps, newIndex, installedBasenames);

      const firstOpt = parsedConfig.steps[0]?.groups[0]?.options[0];
      const firstGrp = parsedConfig.steps[0]?.groups[0];
      const firstStep = parsedConfig.steps[0];
      if (firstOpt) {
        updateOptionPreview(firstOpt, firstStep, firstGrp, newIndex, parsedConfig.moduleHeaderImage);
      } else {
        updateOptionPreview(null, null, null, newIndex, parsedConfig.moduleHeaderImage);
      }
    } catch (err: any) {
      console.error(err);
      setErrorMessage(`Erreur lors du traitement du dossier :\n\n${err?.message || err}`);
    } finally {
      setIsLoading(false);
      setStatusMessage('');
    }
  };

  // --- TRAITEMENT ARCHIVE (ZIP, RAR, 7Z, TAR, etc.) ---
  const handleArchiveFile = async (file: File) => {
    setIsLoading(true);
    setErrorMessage(null);
    setStatusMessage(`Ouverture de ${file.name}...`);
    try {
      const { index, moduleConfigXml, infoXml } = await extractAnyArchive(file, (msg) => {
        setStatusMessage(msg);
      });

      if (!moduleConfigXml) {
        setErrorMessage(
          `Impossible de trouver le fichier "fomod/ModuleConfig.xml" dans l'archive "${file.name}".\n\n` +
          `Vérifiez que cette archive contient bien la structure d'un installateur FOMOD Skyrim.`
        );
        setIsLoading(false);
        return;
      }

      setStatusMessage('Génération des étapes et des options...');
      const parsedConfig = parseModuleConfigXml(moduleConfigXml);
      const parsedInfo = infoXml
        ? parseInfoXml(infoXml)
        : {
            name: parsedConfig.moduleName || file.name.replace(/\.[^/.]+$/, ''),
            author: 'Inconnu',
            version: '1.0',
            website: '',
            description: 'Aucune description disponible dans info.xml',
          };

      setModName(parsedConfig.moduleName || file.name.replace(/\.[^/.]+$/, ''));
      setSteps(parsedConfig.steps);
      setRequiredFiles(parsedConfig.requiredInstallFiles);
      setConditionalFileInstalls(parsedConfig.conditionalFileInstalls || []);
      setMetadata(parsedInfo);
      setArchiveIndex(index);
      setCurrentStepIdx(0);
      setModuleHeaderImage(parsedConfig.moduleHeaderImage);

      initSelections(parsedConfig.steps, index, installedBasenames);

      const firstOpt = parsedConfig.steps[0]?.groups[0]?.options[0];
      const firstGrp = parsedConfig.steps[0]?.groups[0];
      const firstStep = parsedConfig.steps[0];
      if (firstOpt) {
        updateOptionPreview(firstOpt, firstStep, firstGrp, index, parsedConfig.moduleHeaderImage);
      } else {
        updateOptionPreview(null, null, null, index, parsedConfig.moduleHeaderImage);
      }
    } catch (err: any) {
      console.error(err);
      setErrorMessage(
        `Une erreur est survenue lors de l'ouverture de l'archive "${file.name}" :\n\n${err?.message || err}`
      );
    } finally {
      setIsLoading(false);
      setStatusMessage('');
    }
  };

  // Helper récursif pour lire les dossiers lâchés par Drag & Drop via FileSystemEntry
  const getFilesFromDataTransfer = async (dataTransfer: DataTransfer): Promise<File[]> => {
    const items = dataTransfer.items;
    if (items && items.length > 0 && typeof (items[0] as any).webkitGetAsEntry === 'function') {
      const queue: any[] = [];
      for (let i = 0; i < items.length; i++) {
        const item = items[i];
        if (item.kind === 'file') {
          const entry = item.webkitGetAsEntry();
          if (entry) queue.push(entry);
        }
      }

      if (queue.length > 0) {
        const files: File[] = [];

        const traverseEntry = async (entry: any, path = ''): Promise<void> => {
          if (entry.isFile) {
            await new Promise<void>((resolve) => {
              entry.file(
                (file: File) => {
                  const relPath = path ? `${path}/${file.name}` : file.name;
                  Object.defineProperty(file, 'webkitRelativePath', {
                    value: relPath,
                    writable: true,
                    configurable: true,
                  });
                  files.push(file);
                  resolve();
                },
                () => resolve()
              );
            });
          } else if (entry.isDirectory) {
            const dirReader = entry.createReader();
            const readEntries = async (): Promise<any[]> => {
              return new Promise<any[]>((resolve) => {
                dirReader.readEntries(
                  (entries: any[]) => resolve(entries),
                  () => resolve([])
                );
              });
            };
            let batch: any[];
            do {
              batch = await readEntries();
              for (const child of batch) {
                await traverseEntry(child, path ? `${path}/${entry.name}` : entry.name);
              }
            } while (batch.length > 0);
          }
        };

        for (const entry of queue) {
          await traverseEntry(entry);
        }

        if (files.length > 0) {
          return files;
        }
      }
    }

    return Array.from(dataTransfer.files || []);
  };

  // --- GESTION DU DRAG & DROP SANS SCINTILLEMENT ---
  const handleDragEnter = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current++;
    if (e.dataTransfer.items && e.dataTransfer.items.length > 0) {
      setIsDragOver(true);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    e.dataTransfer.dropEffect = 'copy';
    setIsDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current--;
    if (dragCounterRef.current <= 0) {
      dragCounterRef.current = 0;
      setIsDragOver(false);
    }
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    dragCounterRef.current = 0;
    setIsDragOver(false);

    try {
      const files = await getFilesFromDataTransfer(e.dataTransfer);
      if (!files || files.length === 0) return;

      if (files.length === 1) {
        const file = files[0];
        const lower = file.name.toLowerCase();
        const isArchive = [
          '.zip',
          '.rar',
          '.7z',
          '.tar',
          '.tar.gz',
          '.tgz',
          '.gz',
          '.bz2',
        ].some((ext) => lower.endsWith(ext));

        if (isArchive) {
          await handleArchiveFile(file);
          return;
        }
      }

      await handleFolderFiles(files);
    } catch (err: any) {
      console.error('Erreur lors du dépôt de fichier(s):', err);
      setErrorMessage(`Erreur lors de la lecture des fichiers : ${err.message || err}`);
      setIsLoading(false);
    }
  };

  // --- GESTION DES CLICS OPTIONS ---
  const handleSelectRadio = (stepId: string, groupId: string, optionName: string) => {
    setSelections((prev) => ({
      ...prev,
      [stepId]: {
        ...(prev[stepId] || {}),
        [groupId]: optionName,
      },
    }));
    updateActiveFlags(stepId, groupId, optionName, true);
    const step = steps.find((s) => s.id === stepId);
    const grp = step?.groups.find((g) => g.id === groupId);
    const opt = grp?.options.find((o) => o.name === optionName);
    if (opt) handleHoverOption(opt);
  };

  const handleToggleCheck = (stepId: string, groupId: string, optionName: string) => {
    setSelections((prev) => {
      const currentList = (prev[stepId]?.[groupId] as string[]) || [];
      const isSelected = currentList.includes(optionName);
      const nextList = isSelected
        ? currentList.filter((n) => n !== optionName)
        : [...currentList, optionName];

      return {
        ...prev,
        [stepId]: {
          ...(prev[stepId] || {}),
          [groupId]: nextList,
        },
      };
    });
    updateActiveFlags(stepId, groupId, optionName, false);
    const step = steps.find((s) => s.id === stepId);
    const grp = step?.groups.find((g) => g.id === groupId);
    const opt = grp?.options.find((o) => o.name === optionName);
    if (opt) handleHoverOption(opt);
  };

  const updateActiveFlags = (
    stepId: string,
    groupId: string,
    optionName: string,
    isRadio: boolean
  ) => {
    const step = steps.find((s) => s.id === stepId);
    const grp = step?.groups.find((g) => g.id === groupId);
    const opt = grp?.options.find((o) => o.name === optionName);
    if (!opt) return;

    setActiveFlags((prev) => {
      const next = { ...prev };
      if (isRadio) {
        grp?.options.forEach((o) => {
          Object.keys(o.flags).forEach((k) => delete next[k]);
        });
      }
      Object.assign(next, opt.flags);
      return next;
    });
  };

  const collectSelectedOptions = (): FomodOption[] => {
    const list: FomodOption[] = [];

    steps.forEach((step) => {
      const stepSel = selections[step.id] || {};
      step.groups.forEach((grp) => {
        const val = stepSel[grp.id];
        if (grp.type === 'SelectExactlyOne') {
          if (typeof val === 'string' && val !== '__none__') {
            const opt = grp.options.find((o) => o.name === val);
            if (opt) list.push(opt);
          }
        } else {
          if (Array.isArray(val)) {
            val.forEach((name) => {
              const opt = grp.options.find((o) => o.name === name);
              if (opt) list.push(opt);
            });
          }
        }
      });
    });

    return list;
  };

  // Générateur de Staging : COPIE PHYSIQUE DIRECTE DANS LE RÉPERTOIRE SÉLECTIONNÉ
  // Les fichiers sont écrits directement dans le dossier choisi (pas de sous-dossier "Staging").
  const handleGenerateStaging = async () => {
    const selectedOpts = collectSelectedOptions();
    if (selectedOpts.length === 0) {
      alert('Avertissement : Aucune option sélectionnée.');
      return;
    }

    const res = buildStaging(
      selectedOpts,
      requiredFiles,
      archiveIndex,
      stagingDirPath,
      conditionalFileInstalls,
      activeFlags,
      installedBasenames
    );
    setStagingResult(res);
    setDirectWriteSuccess(false);

    // 1. Si un dossier local est déjà lié
    if (stagingDirectoryHandle) {
      try {
        setIsLoading(true);
        setStatusMessage(`Copie directe des ${res.totalCopied} fichiers vers "${stagingDirectoryHandle.name}"...`);
        await writeStagingToLocalDirectoryHandle(stagingDirectoryHandle, res);
        setIsLoading(false);
        setStatusMessage('');
        setDirectWriteSuccess(true);
        setStagingModalOpen(true);
        return;
      } catch (writeErr) {
        setIsLoading(false);
        setStatusMessage('');
        console.error('Erreur écriture locale directe:', writeErr);
        alert('Erreur lors de la copie des fichiers dans le dossier : ' + writeErr);
        setStagingModalOpen(true);
        return;
      }
    }

    // 2. Si pas encore de dossier lié, demander le dossier à l'utilisateur
    if ('showDirectoryPicker' in window) {
      try {
        // @ts-expect-error File System Access API
        const picked: FileSystemDirectoryHandle = await window.showDirectoryPicker({ mode: 'readwrite' });
        setStagingDirectoryHandle(picked);
        setStagingDirPath(`/${picked.name}`);

        setIsLoading(true);
        setStatusMessage(`Copie directe des ${res.totalCopied} fichiers vers "${picked.name}"...`);
        await writeStagingToLocalDirectoryHandle(picked, res);
        setIsLoading(false);
        setStatusMessage('');
        setDirectWriteSuccess(true);
        setStagingModalOpen(true);
        return;
      } catch (err: unknown) {
        const errorName = (err as { name?: string }).name;
        if (errorName === 'AbortError') {
          // L'utilisateur a simplement fermé la fenêtre
          return;
        }
        console.warn('showDirectoryPicker bloqué ou indisponible :', err);
        setFolderSelectModalOpen(true);
        return;
      }
    }

    // 3. Navigateur sans File System Access API ou bloqué : ouvrir le modal pour choisir le dossier ou ouvrir en onglet
    setFolderSelectModalOpen(true);
  };

  // Navigation
  const currentStep = steps[currentStepIdx];
  const isFirstStep = currentStepIdx <= 0;
  const isLastStep = currentStepIdx >= steps.length - 1;

  const handleNextStep = () => {
    if (!isLastStep) {
      const nextIdx = currentStepIdx + 1;
      setCurrentStepIdx(nextIdx);
      const nextS = steps[nextIdx];
      if (nextS) {
        let selOpt: FomodOption | null = null;
        const stepSel = selections[nextS.id] || {};
        for (const grp of nextS.groups) {
          const val = stepSel[grp.id];
          if (typeof val === 'string' && val !== '__none__') {
            selOpt = grp.options.find((o) => o.name === val) || null;
            if (selOpt) break;
          } else if (Array.isArray(val) && val.length > 0) {
            selOpt = grp.options.find((o) => o.name === val[0]) || null;
            if (selOpt) break;
          }
        }
        handleHoverOption(selOpt || nextS.groups[0]?.options[0]);
      }
    }
  };

  const handlePrevStep = () => {
    if (!isFirstStep) {
      const prevIdx = currentStepIdx - 1;
      setCurrentStepIdx(prevIdx);
      const prevS = steps[prevIdx];
      if (prevS) {
        let selOpt: FomodOption | null = null;
        const stepSel = selections[prevS.id] || {};
        for (const grp of prevS.groups) {
          const val = stepSel[grp.id];
          if (typeof val === 'string' && val !== '__none__') {
            selOpt = grp.options.find((o) => o.name === val) || null;
            if (selOpt) break;
          } else if (Array.isArray(val) && val.length > 0) {
            selOpt = grp.options.find((o) => o.name === val[0]) || null;
            if (selOpt) break;
          }
        }
        handleHoverOption(selOpt || prevS.groups[0]?.options[0]);
      }
    }
  };

  // Resizable Panes logic (Sash drag)
  const handleMouseDownSash = (sashIndex: number) => {
    draggingSashRef.current = sashIndex;
    document.addEventListener('mousemove', handleMouseMove);
    document.addEventListener('mouseup', handleMouseUp);
  };

  const handleMouseMove = (e: MouseEvent) => {
    if (draggingSashRef.current === null || !containerRef.current) return;
    const rect = containerRef.current.getBoundingClientRect();
    const totalW = rect.width;
    const clientX = e.clientX - rect.left;
    const currentPercent = (clientX / totalW) * 100;

    setColWidths((prev) => {
      const idx = draggingSashRef.current!;
      if (idx === 0) {
        const newLeft = Math.max(12, Math.min(35, currentPercent));
        const diff = newLeft - prev[0];
        const newMiddle = Math.max(20, prev[1] - diff);
        return [newLeft, newMiddle, prev[2]];
      } else {
        const leftW = prev[0];
        const newMiddle = Math.max(20, Math.min(60, currentPercent - leftW));
        const newRight = Math.max(25, 100 - leftW - newMiddle);
        return [leftW, newMiddle, newRight];
      }
    });
  };

  const handleMouseUp = () => {
    draggingSashRef.current = null;
    document.removeEventListener('mousemove', handleMouseMove);
    document.removeEventListener('mouseup', handleMouseUp);
  };

  return (
    <div
      className="h-screen w-screen bg-[#1e1e1e] text-[#ddd] flex flex-col overflow-hidden select-none p-3 font-sans relative"
      onDragEnter={handleDragEnter}
      onDragOver={handleDragOver}
      onDragLeave={handleDragLeave}
      onDrop={handleDrop}
    >
      {/* Hidden file inputs */}
      <input
        type="file"
        ref={archiveInputRef}
        accept=".zip,.7z,.rar,.tar,.gz,.tgz,.bz2,application/*,*/*"
        className="hidden"
        onChange={(e) => {
          if (e.target.files && e.target.files[0]) {
            const file = e.target.files[0];
            e.target.value = '';
            handleArchiveFile(file);
          }
        }}
      />
      <input
        type="file"
        ref={folderInputRef}
        // @ts-expect-error webkitdirectory is standard in browsers
        webkitdirectory="true"
        className="hidden"
        onChange={(e) => {
          if (e.target.files && e.target.files.length > 0) {
            const files = e.target.files;
            e.target.value = '';
            handleFolderFiles(files);
          }
        }}
      />

      {/* OVERLAY DE DRAG & DROP GLOBAL */}
      {isDragOver && (
        <div className="fixed inset-0 z-50 bg-[#0ea5e9]/25 border-4 border-dashed border-[#0ea5e9] flex items-center justify-center backdrop-blur-xs pointer-events-none">
          <div className="bg-[#1e1e1e] px-8 py-6 rounded-xl shadow-2xl border border-[#0ea5e9] text-center">
            <div className="text-5xl mb-2">📥</div>
            <div className="text-lg font-bold text-white">Déposez l'archive (ZIP, RAR, 7Z) du mod FOMOD ici</div>
            <div className="text-xs text-[#0ea5e9] mt-1 font-medium">Extraction et analyse instantanées</div>
          </div>
        </div>
      )}

      {/* OVERLAY DE CHARGEMENT & PROGRESSION */}
      {isLoading && (
        <div className="fixed inset-0 z-50 bg-black/80 flex items-center justify-center backdrop-blur-xs p-4">
          <div className="bg-[#222222] border border-[#38bdf8]/60 rounded-xl p-6 max-w-md w-full shadow-2xl flex flex-col items-center text-center">
            <div className="w-12 h-12 border-4 border-[#38bdf8]/20 border-t-[#38bdf8] rounded-full animate-spin mb-4" />
            <div className="text-base font-bold text-white mb-2">{strings.loading.title}</div>
            <div className="text-xs text-[#38bdf8] font-mono mb-3 bg-[#181818] px-3 py-2 rounded border border-[#333] w-full truncate text-center">
              {statusMessage || strings.loading.inProgress}
            </div>
            <div className="text-[11px] text-[#888]">
              {strings.loading.sub}
            </div>
          </div>
        </div>
      )}

      {/* MODAL D'ERREUR VISIBLE AVEC CONSEILS */}
      {errorMessage && (
        <div className="fixed inset-0 z-50 bg-black/85 flex items-center justify-center p-4">
          <div className="bg-[#242424] border border-red-500/70 rounded-xl p-6 max-w-lg w-full shadow-2xl text-left">
            <div className="flex items-center gap-3 mb-3 text-red-400">
              <span className="text-2xl">⚠️</span>
              <div className="text-base font-bold text-white">{strings.error.cannotLoad}</div>
            </div>
            <div className="bg-[#181818] border border-[#333] p-3 rounded text-xs text-[#ddd] leading-relaxed mb-4 whitespace-pre-wrap max-h-48 overflow-y-auto font-mono">
              {errorMessage}
            </div>
            <div className="text-xs text-[#999] mb-5 space-y-1.5 bg-[#1e1e1e] p-3 rounded border border-[#303030]">
              <div className="font-semibold text-[#ddd]">{strings.error.tipsTitle}</div>
              <div>• {strings.error.tip1}</div>
              <div>• {strings.error.tip2}</div>
            </div>
            <div className="flex justify-end gap-3">
              <button
                type="button"
                onClick={() => setErrorMessage(null)}
                className="px-5 py-2 bg-[#fbbf24] hover:bg-[#f59e0b] text-[#1a1a1a] font-bold text-xs rounded transition-colors cursor-pointer"
              >
                {strings.common.close}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ============================================================ */}
      {/* HEADER : TITRE DU MOD (Style Vortex / NMM) */}
      {/* ============================================================ */}
      <header className="h-10 bg-[#262626] border border-[#333333] flex items-center justify-between px-3 mb-2 rounded shrink-0">
        <div className="flex items-center gap-2 overflow-hidden">
          <span className="text-[#fbbf24] text-sm">⚡</span>
          <h1
            className="text-sm font-bold text-white tracking-wide truncate max-w-[800px]"
            title={steps.length > 0 ? modName : strings.header.title}
          >
            {steps.length > 0 ? modName : strings.header.title}
          </h1>
        </div>
        <div className="flex items-center gap-2.5 shrink-0 text-xs font-mono text-[#888]">
          <LanguageSelector variant="dropdown" />
          <span className="text-[#555]">|</span>
          {steps.length > 0 ? (
            <>
              <button
                onClick={handleCloseMod}
                className="px-2.5 py-1 bg-[#333333] hover:bg-[#404040] active:bg-[#222] text-[#ddd] hover:text-white text-xs rounded border border-[#444] flex items-center gap-1.5 cursor-pointer transition-colors"
                title={strings.header.closeModTooltip}
              >
                <span>⬅</span>
                <span>{strings.header.closeMod}</span>
              </button>
              <span className="text-[#555]">|</span>
              <span>
                {strings.common.step} {currentStepIdx + 1} / {steps.length}
              </span>
              <span className="text-[#555]">|</span>
              <span className="text-[#aaa] text-[11px]">
                {activeFlags && Object.keys(activeFlags).length > 0
                  ? `${Object.keys(activeFlags).length} ${strings.common.activeFlags}`
                  : 'Skyrim SE/AE'}
              </span>
            </>
          ) : (
            <span className="text-[#aaa] text-[11px]">{strings.header.waitingArchive}</span>
          )}
        </div>
      </header>

      {/* ============================================================ */}
      {/* CORPS PRINCIPAL : ACCUEIL mTranslator OU 3 COLONNES */}
      {/* ============================================================ */}
      {steps.length === 0 ? (
        <div className="flex-1 flex flex-col items-center justify-center p-6 bg-[#181818] rounded border border-[#2c2c2c] relative overflow-hidden select-none">
          <div className="max-w-xl w-full bg-[#202020] border border-[#333333] rounded-lg shadow-2xl p-8 flex flex-col items-center text-center">
            {/* Choix de langue centré */}
            <div className="w-full flex items-center justify-center mb-5 pb-3 border-b border-[#2d2d2d]">
              <LanguageSelector variant="pills" />
            </div>

            {/* Logo / Icône */}
            <div className="w-16 h-16 rounded-full bg-[#262626] border border-[#3d3d3d] flex items-center justify-center text-3xl mb-4 shadow-inner">
              📦
            </div>

            <h2 className="text-xl font-bold text-white tracking-wide mb-1">
              {strings.welcome.title}
            </h2>
            <p className="text-xs text-[#999999] max-w-md mb-6 leading-relaxed">
              {strings.welcome.subtitle}
            </p>

            {/* Zone de Drag & Drop principale */}
            <div
              onClick={() => archiveInputRef.current?.click()}
              className={`w-full border-2 border-dashed rounded-lg p-7 flex flex-col items-center justify-center gap-3 cursor-pointer transition-all ${
                isDragOver
                  ? 'border-[#38bdf8] bg-[#38bdf8]/15 shadow-[0_0_25px_rgba(56,189,248,0.3)]'
                  : 'border-[#444444] bg-[#1a1a1a] hover:border-[#38bdf8]/60 hover:bg-[#1f2428]'
              }`}
            >
              <div className="text-3xl text-[#888]">📥</div>
              <div className="text-sm font-semibold text-[#f1f1f1]">
                {strings.welcome.dropTitle}
              </div>
              <div className="text-[11px] text-[#777]">
                {strings.welcome.supportedFormats} <span className="text-[#38bdf8] font-mono font-semibold">.ZIP</span>,{' '}
                <span className="text-[#38bdf8] font-mono font-semibold">.7Z</span>,{' '}
                <span className="text-[#38bdf8] font-mono font-semibold">.RAR</span> {strings.welcome.orFolder}
              </div>

              {/* Bouton principal de chargement d'archive */}
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  archiveInputRef.current?.click();
                }}
                className="mt-2 px-6 py-2.5 bg-[#fbbf24] hover:bg-[#f59e0b] active:bg-[#d97706] text-[#1a1a1a] font-bold text-xs rounded transition-colors flex items-center gap-2 shadow-md cursor-pointer"
              >
                <span className="text-base">📁</span>
                <span>{strings.welcome.loadArchiveBtn}</span>
              </button>
            </div>

            {/* Actions secondaires */}
            <div className="flex items-center justify-center gap-4 mt-4 w-full text-xs text-[#888]">
              <button
                type="button"
                onClick={() => folderInputRef.current?.click()}
                className="hover:text-white transition-colors flex items-center gap-1.5 cursor-pointer underline underline-offset-4"
              >
                <span>📂</span>
                <span>{strings.welcome.loadFolderBtn}</span>
              </button>
              <span>•</span>
              <button
                type="button"
                onClick={() => loadSampleMod(SAMPLE_MOD_CBBE)}
                className="hover:text-[#38bdf8] transition-colors flex items-center gap-1.5 cursor-pointer underline underline-offset-4"
              >
                <span>🧪</span>
                <span>{strings.welcome.loadDemoBtn}</span>
              </button>
            </div>

            {/* Pied de carte informatif style mTranslator */}
            <div className="mt-8 pt-4 border-t border-[#2e2e2e] w-full text-[11px] text-[#666] flex justify-between items-center">
              <span>{strings.welcome.standaloneEngine}</span>
              <span>{strings.welcome.noGameRequired}</span>
            </div>
          </div>
        </div>
      ) : (
      <div
        ref={containerRef}
        className="flex-1 flex overflow-hidden w-full relative min-h-0"
      >
        {/* ============================================================ */}
        {/* 1. COLONNE GAUCHE (CONTRÔLES, ACTIONS & DOSSIER CIBLE) ~26% */}
        {/* ============================================================ */}
        <div
          style={{ width: `${colWidths[0]}%` }}
          className="h-full min-w-[200px] bg-[#262626] border border-[#333333] flex flex-col justify-between p-2 overflow-y-auto shrink-0 select-none"
        >
          {/* Haut : Boutons Principaux & Configuration Data */}
          <div className="space-y-2">
            {/* Bouton Ouvrir un FOMOD : Hauteur ajustée (h-14), gap équilibré */}
            <button
              onClick={() => setOpenModModalOpen(true)}
              className="w-full h-14 px-3 bg-[#fbbf24] hover:bg-[#f59e0b] active:bg-[#d97706] text-[#1a1a1a] font-bold text-sm rounded transition-colors flex items-center justify-center gap-1.5 cursor-pointer shadow-xs whitespace-nowrap"
              title={strings.sidebar.openFomodTooltip}
            >
              <span className="text-xl">📦</span>
              <span>{strings.sidebar.openFomod}</span>
            </button>

            {/* Infos du Mod */}
            <button
              onClick={() => setInfoModalOpen(true)}
              className="w-full py-2 px-3 bg-[#444444] hover:bg-[#505050] text-white text-xs font-medium rounded transition-colors flex items-center justify-center gap-1.5 cursor-pointer whitespace-nowrap"
            >
              <span>ℹ️</span>
              <span>{strings.sidebar.modInfo}</span>
            </button>

            {/* Bouton Choisir dossier Data */}
            <button
              onClick={() => setDataModalOpen(true)}
              className="w-full py-2 px-3 bg-[#333333] hover:bg-[#404040] text-white text-xs font-medium rounded transition-colors flex items-center justify-center gap-1.5 cursor-pointer border border-[#444444] whitespace-nowrap"
            >
              <span>📂</span>
              <span>{strings.sidebar.chooseDataDir}</span>
            </button>

            {/* État du dossier Data */}
            <div className="text-[11px] text-[#bbb] px-1 py-1 leading-snug break-words text-center">
              {dataDirPath ? (
                <>
                  <span className="font-semibold text-[#ddd]">{strings.common.dataFolder}</span> {dataDirPath}
                  <br />
                  <span className="text-[#38bdf8]">
                    ({installedBasenames.size} {strings.common.filesDetected})
                  </span>
                </>
              ) : (
                <>
                  <span className="font-semibold text-[#ddd]">{strings.common.dataFolder}</span>{' '}
                  <span className="italic">{strings.common.notSet}</span>
                  <br />
                  <span className="text-[#888] text-[10px]">
                    {strings.common.clickToSimulate}
                  </span>
                </>
              )}
            </div>
          </div>

          {/* Bas : Destination & Génération directe */}
          <div className="pt-3 border-t border-[#333333] space-y-2">
            {/* Bouton Choisir le dossier */}
            <button
              onClick={() => setFolderSelectModalOpen(true)}
              className="w-full py-2 px-3 bg-[#333333] hover:bg-[#404040] text-white text-xs font-semibold rounded transition-colors flex items-center justify-center gap-1.5 cursor-pointer border border-[#444444] whitespace-nowrap"
            >
              <span>📁</span>
              <span>{strings.sidebar.chooseStagingDir}</span>
            </button>

            {/* Affichage du dossier cible direct */}
            <div
              className="text-[11px] text-[#bbb] text-center px-1.5 py-1.5 bg-[#1a1a1a] rounded border border-[#2a2a2a] truncate font-mono"
              title={stagingDirPath}
            >
              <span className="text-[#888] block text-[10px]">{strings.common.destination}</span>
              <span className="text-[#38bdf8] font-medium truncate block">{stagingDirPath}</span>
            </div>

            {/* Bouton Action Blue : Générer le Staging */}
            <button
              onClick={handleGenerateStaging}
              className="w-full py-2.5 px-3 bg-[#0ea5e9] hover:bg-[#0284c7] active:bg-[#0369a1] text-white font-bold text-xs tracking-wide uppercase rounded transition-colors flex items-center justify-center gap-1 cursor-pointer shadow-sm mt-1 whitespace-nowrap"
            >
              <span>{strings.sidebar.generateStaging}</span>
            </button>
          </div>
        </div>

        {/* SASH 0 (Divider 1) */}
        <div
          onMouseDown={() => handleMouseDownSash(0)}
          className="w-2 hover:w-2.5 bg-[#1e1e1e] hover:bg-[#0ea5e9]/50 transition-colors cursor-col-resize shrink-0 flex items-center justify-center"
        >
          <div className="w-0.5 h-8 bg-[#444] rounded-full" />
        </div>

        {/* ============================================================ */}
        {/* 2. COLONNE CENTRALE (OPTIONS & NAVIGATION) ~30% */}
        {/* AUCUNE TRADUCTION ICI : NOMS ORIGINAUX DU FOMOD STRICTEMENT CONSERVÉS */}
        {/* ============================================================ */}
        <div
          style={{ width: `${colWidths[1]}%` }}
          className="h-full bg-[#222222] border border-[#333333] flex flex-col justify-between shrink-0 overflow-hidden"
        >
          {/* Zone de contenu défilante */}
          <div className="flex-1 overflow-y-auto p-3 space-y-4">
            {isLoading ? (
              <div className="flex flex-col items-center justify-center h-48 text-[#aaa] text-sm">
                <div className="animate-spin text-2xl mb-2">⏳</div>
                <div>{statusMessage || 'Chargement du mod...'}</div>
              </div>
            ) : steps.length === 0 ? (
              <div className="flex flex-col items-center justify-center h-48 text-[#888] text-xs text-center p-4">
                <div className="text-3xl mb-2">📁</div>
                <div>{strings.steps.noStepsFound}</div>
                <button
                  onClick={() => loadSampleMod(SAMPLE_MOD_CBBE)}
                  className="mt-3 px-3 py-1.5 bg-[#333333] hover:bg-[#444444] text-white text-xs rounded cursor-pointer"
                >
                  {strings.steps.loadDemoAction}
                </button>
              </div>
            ) : currentStep ? (
              <div>
                {/* Step Title - Original FOMOD */}
                <div className="pb-2 mb-3 border-b border-[#333333]">
                  <div className="flex items-center justify-between">
                    <h2 className="text-sm font-bold text-white tracking-wide">
                      {currentStep.derivedLabel}
                    </h2>
                    <span className="text-[11px] text-[#888] font-mono">
                      {currentStepIdx + 1} / {steps.length}
                    </span>
                  </div>
                </div>

                {/* Groups */}
                <div className="space-y-4">
                  {currentStep.groups.map((group) => {
                    const isSingle = group.type === 'SelectExactlyOne';
                    const currentVal = selections[currentStep.id]?.[group.id];

                    return (
                      <div
                        key={group.id}
                        className="bg-[#222222] border-none rounded p-3"
                      >
                        {/* Group Header Label - Original FOMOD */}
                        <div className="text-xs font-bold text-[#ddd] mb-2.5 pb-1 border-none flex items-center justify-between">
                          <span>{group.name}</span>
                          <span className="text-[10px] font-normal text-[#888]">
                            {isSingle ? strings.common.singleChoice : strings.common.multipleChoice}
                          </span>
                        </div>

                        {/* Group Options */}
                        <div className="space-y-1.5">
                          {group.options.map((opt) => {
                            const isSelected = isSingle
                              ? currentVal === opt.name
                              : Array.isArray(currentVal) && currentVal.includes(opt.name);

                            // Dependency auto-select match indicator
                            const matchesDep = isOptionRecommended(opt, installedBasenames, activeFlags);

                            return (
                              <div
                                key={opt.id}
                                onMouseEnter={() => handleHoverOption(opt)}
                                onClick={() => {
                                  handleHoverOption(opt);
                                  if (isSingle) {
                                    handleSelectRadio(currentStep.id, group.id, opt.name);
                                  } else {
                                    handleToggleCheck(currentStep.id, group.id, opt.name);
                                  }
                                }}
                                className={`flex items-start gap-2.5 px-2 py-1.5 rounded cursor-pointer transition-colors ${
                                  isSelected
                                    ? 'bg-[#2a2a2a] text-white'
                                    : 'hover:bg-[#282828] text-[#ccc]'
                                }`}
                              >
                                {/* Custom radio or checkbox */}
                                <div className="pt-0.5 shrink-0">
                                  {isSingle ? (
                                    <div
                                      className={`w-4 h-4 rounded-full border flex items-center justify-center transition-colors ${
                                        isSelected
                                          ? 'border-[#0ea5e9] bg-[#0ea5e9]'
                                          : 'border-[#555] bg-[#222]'
                                      }`}
                                    >
                                      {isSelected && (
                                        <div className="w-1.5 h-1.5 rounded-full bg-white" />
                                      )}
                                    </div>
                                  ) : (
                                    <div
                                      className={`w-4 h-4 rounded border flex items-center justify-center transition-colors ${
                                        isSelected
                                          ? 'border-[#0ea5e9] bg-[#0ea5e9]'
                                          : 'border-[#555] bg-[#222]'
                                      }`}
                                    >
                                      {isSelected && (
                                        <span className="text-white text-[11px] font-bold leading-none">
                                          ✓
                                        </span>
                                      )}
                                    </div>
                                  )}
                                </div>

                                <div className="flex-1 text-xs select-none">
                                  <div className="flex items-center justify-between">
                                    <span className="font-medium leading-tight">{opt.name}</span>
                                    {matchesDep && (
                                      <span
                                        className="text-[9px] px-1 py-0.2 bg-[#0ea5e9]/20 text-[#38bdf8] rounded border border-[#0ea5e9]/30"
                                        title={strings.steps.autoDetected}
                                      >
                                        {strings.common.auto}
                                      </span>
                                    )}
                                  </div>
                                </div>
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>
              </div>
            ) : null}
          </div>

          {/* Navigation Bar (RETOUR / CONTINUER) */}
          <div className="p-3 border-t border-[#333333] flex gap-2.5 bg-[#222222]">
            <button
              onClick={handlePrevStep}
              disabled={isFirstStep || steps.length === 0}
              className="flex-1 py-2.5 px-4 bg-[#333333] hover:bg-[#404040] disabled:opacity-40 disabled:hover:bg-[#333333] text-white font-bold text-xs uppercase tracking-wide rounded transition-colors cursor-pointer disabled:cursor-not-allowed text-center"
            >
              {strings.steps.prevStep}
            </button>

            <button
              onClick={handleNextStep}
              disabled={isLastStep || steps.length === 0}
              className="flex-1 py-2.5 px-4 bg-[#0ea5e9] hover:bg-[#0284c7] disabled:opacity-40 disabled:hover:bg-[#0ea5e9] text-white font-bold text-xs uppercase tracking-wide rounded transition-colors cursor-pointer disabled:cursor-not-allowed text-center"
            >
              {strings.steps.nextStep}
            </button>
          </div>
        </div>

        {/* SASH 1 (Divider 2) */}
        <div
          onMouseDown={() => handleMouseDownSash(1)}
          className="w-2 hover:w-2.5 bg-[#1e1e1e] hover:bg-[#0ea5e9]/50 transition-colors cursor-col-resize shrink-0 flex items-center justify-center"
        >
          <div className="w-0.5 h-8 bg-[#444] rounded-full" />
        </div>

        {/* ============================================================ */}
        {/* 3. COLONNE DROITE (DESCRIPTION & IMAGE APERÇU) ~45% */}
        {/* ============================================================ */}
        <div
          style={{ width: `${colWidths[2]}%` }}
          className="h-full bg-[#222222] border border-[#333333] flex flex-col p-5 overflow-y-auto shrink-0 select-none"
        >
          {/* Titre & Description Text agrandie pour meilleure lisibilité */}
          <div className="mb-4">
            <div className="text-xs font-bold uppercase tracking-wider text-[#888] mb-2 flex items-center gap-1.5">
              <span>📖</span> {strings.preview.instructionsTitle}
            </div>
            <div className="text-sm md:text-[15px] text-[#f1f1f1] leading-relaxed whitespace-pre-wrap font-sans min-h-[4rem] bg-[#1a1a1a]/60 p-3.5 rounded border-none">
              {previewDesc}
            </div>
          </div>

          {/* Image Preview Container aligné en haut sous le bloc d'instructions */}
          <div className="w-full flex flex-col items-center justify-start overflow-hidden">
            <div
              onClick={() => setFullPreviewModalOpen(true)}
              className="group relative w-full max-h-[560px] bg-[#1a1a1a] border border-[#333333] hover:border-[#0ea5e9] rounded p-1 cursor-pointer transition-all flex items-center justify-center overflow-hidden shadow-md"
              title={strings.preview.clickToEnlarge}
            >
              <img
                src={previewImgUrl || createSvgPlaceholder(strings.preview.defaultTitle, strings.preview.defaultSubtitle, '#1e293b', '#38bdf8')}
                alt={strings.preview.defaultTitle}
                className="max-h-[520px] max-w-full object-contain rounded select-none transition-transform group-hover:scale-[1.01]"
              />
              <div className="absolute bottom-2 right-2 px-2 py-1 bg-black/75 text-[10px] text-[#aaa] rounded opacity-0 group-hover:opacity-100 transition-opacity">
                {strings.preview.enlarge}
              </div>
            </div>
          </div>
        </div>
      </div>
      )}

      {/* MODALS */}
      <ModInfoModal
        isOpen={infoModalOpen}
        onClose={() => setInfoModalOpen(false)}
        metadata={{
          ...metadata,
          name: metadata.name || modName,
          description: metadata.description,
        }}
      />

      <ImagePreviewModal
        isOpen={fullPreviewModalOpen}
        onClose={() => setFullPreviewModalOpen(false)}
        imageUrl={previewImgUrl}
        title={modName}
      />

      <DataDirModal
        isOpen={dataModalOpen}
        onClose={() => setDataModalOpen(false)}
        currentDataPath={dataDirPath}
        detectedPlugins={installedBasenames}
        onApplyData={(path, plugins) => {
          setDataDirPath(path);
          setInstalledBasenames(plugins);
          initSelections(steps, archiveIndex, plugins, true);
        }}
      />

      <FolderSelectModal
        isOpen={folderSelectModalOpen}
        onClose={() => setFolderSelectModalOpen(false)}
        currentPath={stagingDirPath}
        onSelectDirectoryHandle={(handle) => {
          setStagingDirectoryHandle(handle);
          setStagingDirPath(`/${handle.name}`);
        }}
        onSetCustomPath={(newPath) => {
          setStagingDirPath(newPath);
        }}
      />

      <StagingResultModal
        isOpen={stagingModalOpen}
        onClose={() => setStagingModalOpen(false)}
        result={stagingResult}
        stagingPathDisplay={stagingDirPath}
        directWriteSuccess={directWriteSuccess}
      />

      <OpenModModal
        isOpen={openModModalOpen}
        onClose={() => setOpenModModalOpen(false)}
        onSelectArchive={() => archiveInputRef.current?.click()}
        onSelectFolder={() => folderInputRef.current?.click()}
        onLoadSample={(sampleId) => {
          if (sampleId === 'cbbe') {
            loadSampleMod(SAMPLE_MOD_CBBE);
          } else if (sampleId === 'smim') {
            loadSampleMod(SAMPLE_MOD_SMIM);
          }
        }}
      />
    </div>
  );
}
