export interface FomodFileItem {
  source: string;
  destination: string;
  priority?: number;
  alwaysInstall?: boolean;
  installIfMissing?: boolean;
}

export interface FomodFolderItem {
  source: string;
  destination: string;
  priority?: number;
  alwaysInstall?: boolean;
  installIfMissing?: boolean;
}

export type DependencyOperator = 'And' | 'Or' | 'Not';

export interface FileDependency {
  file: string;
  state: 'Active' | 'Inactive' | 'Missing';
}

export interface FlagDependency {
  flag: string;
  value: string;
}

export interface FomodDependencies {
  operator: DependencyOperator;
  fileDependencies: FileDependency[];
  flagDependencies: FlagDependency[];
  nestedDependencies: FomodDependencies[];
}

export interface TypeDescriptorPattern {
  dependencies?: FomodDependencies;
  typeName: string;
}

export interface TypeDescriptor {
  defaultType: string;
  patterns: TypeDescriptorPattern[];
}

export interface ConditionalInstallPattern {
  dependencies?: FomodDependencies;
  files: FomodFileItem[];
  folders: FomodFolderItem[];
}

export interface FomodOption {
  id: string;
  name: string;
  description: string;
  imagePath?: string;
  files: FomodFileItem[];
  folders: FomodFolderItem[];
  flags: Record<string, string>; // flags set when this option is selected
  dependencies?: FomodDependencies;
  typeDescriptor?: string | TypeDescriptor;
}


export type GroupType =
  | 'SelectExactlyOne'
  | 'SelectAtLeastOne'
  | 'SelectAtMostOne'
  | 'SelectAny'
  | 'SelectAll';

export interface FomodGroup {
  id: string;
  name: string;
  type: GroupType;
  options: FomodOption[];
  headerImage?: string;
  imagePath?: string;
}

export interface FomodStep {
  id: string;
  name: string;
  derivedLabel: string;
  groups: FomodGroup[];
  headerImage?: string;
  imagePath?: string;
}

export interface FomodMetadata {
  name: string;
  author: string;
  version: string;
  website: string;
  description: string;
}

export interface VirtualFileEntry {
  path: string; // relative path in archive
  isDir: boolean;
  size?: number;
  blob?: Blob;
  data?: Uint8Array;
  url?: string; // object URL for images
  getBlob?: () => Promise<Blob>;
}

export interface ArchiveIndex {
  files: Map<string, VirtualFileEntry>; // lowercase relative path -> entry
  dirs: Map<string, string>; // lowercase relative path -> original path
}

export interface StagingItem {
  sourcePath: string;
  destinationPath: string;
  type: 'file' | 'folder';
  size: number;
  matchedFromOption: string;
  priority?: number;
  blob?: Blob;
}

export interface StagingResult {
  items: StagingItem[];
  log: string[];
  totalCopied: number;
  totalMissing: number;
  totalSize: number;
  stagingDirName: string;
}
