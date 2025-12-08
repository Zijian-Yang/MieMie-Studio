import { create } from 'zustand';
import type { Project, Character, Scene, Prop, ScriptScene } from '../types';
import { projectsApi } from '../services/api';

interface AppState {
  // 当前项目
  currentProject: Project | null;
  projects: Project[];
  
  // 加载状态
  loading: boolean;
  
  // 操作
  setCurrentProject: (project: Project | null) => void;
  setProjects: (projects: Project[]) => void;
  loadProjects: () => Promise<void>;
  loadProject: (id: string) => Promise<void>;
  
  // 更新项目内容
  updateScript: (content: string, scenes: ScriptScene[]) => void;
  updateCharacters: (characters: Character[]) => void;
  updateScenes: (scenes: Scene[]) => void;
  updateProps: (props: Prop[]) => void;
}

export const useAppStore = create<AppState>((set, get) => ({
  currentProject: null,
  projects: [],
  loading: false,

  setCurrentProject: (project) => set({ currentProject: project }),
  
  setProjects: (projects) => set({ projects }),
  
  loadProjects: async () => {
    set({ loading: true });
    try {
      const { projects } = await projectsApi.list();
      set({ projects, loading: false });
    } catch (error) {
      console.error('Failed to load projects:', error);
      set({ loading: false });
    }
  },
  
  loadProject: async (id: string) => {
    set({ loading: true });
    try {
      const project = await projectsApi.get(id);
      set({ currentProject: project, loading: false });
    } catch (error) {
      console.error('Failed to load project:', error);
      set({ loading: false });
    }
  },
  
  updateScript: (content, scenes) => {
    const { currentProject } = get();
    if (!currentProject) return;
    
    set({
      currentProject: {
        ...currentProject,
        script: currentProject.script
          ? { ...currentProject.script, processed_content: content, scenes }
          : {
              id: '',
              project_id: currentProject.id,
              title: '',
              original_content: '',
              processed_content: content,
              scenes,
              created_at: new Date().toISOString(),
              updated_at: new Date().toISOString(),
            },
      },
    });
  },
  
  updateCharacters: (characters) => {
    const { currentProject } = get();
    if (!currentProject) return;
    
    set({
      currentProject: {
        ...currentProject,
        characters,
      },
    });
  },
  
  updateScenes: (scenes) => {
    const { currentProject } = get();
    if (!currentProject) return;
    
    set({
      currentProject: {
        ...currentProject,
        scenes,
      },
    });
  },
  
  updateProps: (props) => {
    const { currentProject } = get();
    if (!currentProject) return;
    
    set({
      currentProject: {
        ...currentProject,
        props,
      },
    });
  },
}));

