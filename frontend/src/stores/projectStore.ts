import { create } from 'zustand'
import { Project, projectsApi } from '../services/api'

interface ProjectState {
  projects: Project[]
  currentProject: Project | null
  loading: boolean
  error: string | null
  
  // Actions
  fetchProjects: () => Promise<void>
  fetchProject: (id: string) => Promise<void>
  createProject: (name: string, description?: string) => Promise<Project>
  updateProject: (id: string, data: { name?: string; description?: string }) => Promise<void>
  deleteProject: (id: string) => Promise<void>
  setCurrentProject: (project: Project | null) => void
  clearError: () => void
}

export const useProjectStore = create<ProjectState>((set, get) => ({
  projects: [],
  currentProject: null,
  loading: false,
  error: null,

  fetchProjects: async () => {
    set({ loading: true, error: null })
    try {
      const { projects } = await projectsApi.list()
      set({ projects, loading: false })
    } catch (error) {
      set({ error: (error as Error).message, loading: false })
    }
  },

  fetchProject: async (id: string) => {
    set({ loading: true, error: null })
    try {
      const project = await projectsApi.get(id)
      set({ currentProject: project, loading: false })
    } catch (error) {
      set({ error: (error as Error).message, loading: false })
    }
  },

  createProject: async (name: string, description?: string) => {
    set({ loading: true, error: null })
    try {
      const project = await projectsApi.create({ name, description })
      set((state) => ({
        projects: [project, ...state.projects],
        loading: false,
      }))
      return project
    } catch (error) {
      set({ error: (error as Error).message, loading: false })
      throw error
    }
  },

  updateProject: async (id: string, data: { name?: string; description?: string }) => {
    try {
      const updatedProject = await projectsApi.update(id, data)
      set((state) => ({
        projects: state.projects.map((p) => (p.id === id ? updatedProject : p)),
        currentProject: state.currentProject?.id === id ? updatedProject : state.currentProject,
      }))
    } catch (error) {
      set({ error: (error as Error).message })
      throw error
    }
  },

  deleteProject: async (id: string) => {
    try {
      await projectsApi.delete(id)
      set((state) => ({
        projects: state.projects.filter((p) => p.id !== id),
        currentProject: state.currentProject?.id === id ? null : state.currentProject,
      }))
    } catch (error) {
      set({ error: (error as Error).message })
      throw error
    }
  },

  setCurrentProject: (project: Project | null) => {
    set({ currentProject: project })
  },

  clearError: () => {
    set({ error: null })
  },
}))

