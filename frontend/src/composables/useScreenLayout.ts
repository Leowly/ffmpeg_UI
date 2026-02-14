import { ref, computed, onMounted, onUnmounted } from 'vue'

export interface ScreenLayout {
  width: number
  height: number
  aspectRatio: number
  isMobile: boolean
  isSmallMobile: boolean
  isLandscape: boolean
  spacing: {
    xs: string
    sm: string
    md: string
    lg: string
    xl: string
  }
  fontSize: {
    xs: string
    sm: string
    md: string
    lg: string
    xl: string
  }
  borderRadius: {
    sm: string
    md: string
    lg: string
  }
  layout: {
    sidebarWidth: string
    contentPadding: string
    cardPadding: string
    gap: string
  }
}

export function useScreenLayout() {
  const width = ref(typeof window !== 'undefined' ? window.innerWidth : 1200)
  const height = ref(typeof window !== 'undefined' ? window.innerHeight : 800)

  const handleResize = () => {
    width.value = window.innerWidth
    height.value = window.innerHeight
  }

  onMounted(() => {
    window.addEventListener('resize', handleResize)
    handleResize()
  })

  onUnmounted(() => {
    window.removeEventListener('resize', handleResize)
  })

  const aspectRatio = computed(() => width.value / height.value)

  const isMobile = computed(() => width.value < 768)
  const isSmallMobile = computed(() => width.value < 480)
  const isLandscape = computed(() => width.value > height.value)

  const scaleFactor = computed(() => {
    const baseWidth = 1920
    const normalized = width.value / baseWidth
    return Math.pow(Math.max(0.4, Math.min(1, normalized)), 0.6)
  })

  const heightFactor = computed(() => {
    const baseHeight = 1080
    const normalized = height.value / baseHeight
    return Math.pow(Math.max(0.5, Math.min(1, normalized)), 0.5)
  })

  const combinedFactor = computed(() => {
    return 0.6 * scaleFactor.value + 0.4 * heightFactor.value
  })

  const spacing = computed(() => {
    const minDimension = Math.min(width.value, height.value)
    const base = Math.min(24, minDimension * 0.03)

    return {
      xs: `${(base * 0.25 * combinedFactor.value).toFixed(1)}px`,
      sm: `${(base * 0.5 * combinedFactor.value).toFixed(1)}px`,
      md: `${(base * combinedFactor.value).toFixed(1)}px`,
      lg: `${(base * 1.5 * combinedFactor.value).toFixed(1)}px`,
      xl: `${(base * 2 * combinedFactor.value).toFixed(1)}px`,
    }
  })

  const fontSize = computed(() => {
    const baseFontSize = Math.min(16, 12 + width.value / 120)

    return {
      xs: `${(baseFontSize * 0.75 * combinedFactor.value).toFixed(1)}px`,
      sm: `${(baseFontSize * 0.875 * combinedFactor.value).toFixed(1)}px`,
      md: `${(baseFontSize * combinedFactor.value).toFixed(1)}px`,
      lg: `${(baseFontSize * 1.125 * combinedFactor.value).toFixed(1)}px`,
      xl: `${(baseFontSize * 1.25 * combinedFactor.value).toFixed(1)}px`,
    }
  })

  const borderRadius = computed(() => {
    const base = Math.min(8, Math.min(width.value, height.value) * 0.01)

    return {
      sm: `${(base * 0.5 * combinedFactor.value).toFixed(1)}px`,
      md: `${(base * combinedFactor.value).toFixed(1)}px`,
      lg: `${(base * 1.5 * combinedFactor.value).toFixed(1)}px`,
    }
  })

  const layout = computed(() => {
    const sidebarBaseWidth = Math.min(350, width.value * 0.25)
    const sidebarWidth = isMobile.value
      ? '100%'
      : `${Math.max(250, sidebarBaseWidth * combinedFactor.value)}px`

    const contentPadding = `${(4 * combinedFactor.value).toFixed(1)}px`
    const cardPadding = `${(8 * combinedFactor.value).toFixed(1)}px`
    const gap = `${(8 * combinedFactor.value).toFixed(1)}px`

    return {
      sidebarWidth,
      contentPadding,
      cardPadding,
      gap,
    }
  })

  const screenLayout = computed<ScreenLayout>(() => ({
    width: width.value,
    height: height.value,
    aspectRatio: aspectRatio.value,
    isMobile: isMobile.value,
    isSmallMobile: isSmallMobile.value,
    isLandscape: isLandscape.value,
    spacing: spacing.value,
    fontSize: fontSize.value,
    borderRadius: borderRadius.value,
    layout: layout.value,
  }))

  return {
    width,
    height,
    aspectRatio,
    isMobile,
    isSmallMobile,
    isLandscape,
    scaleFactor,
    spacing,
    fontSize,
    borderRadius,
    layout,
    screenLayout,
  }
}
