import { useDark, useToggle } from '@vueuse/core'

export const isDark = useDark({
    selector: 'html',
    attribute: 'class',
    valueDark: 'dark',
    valueLight: 'light',
    onChanged(dark) {
        const html = document.documentElement
        html.setAttribute('class', dark ? 'dark' : 'light')
        html.style.colorScheme = dark ? 'dark' : 'light'
    }
})

export const toggleDark = useToggle(isDark)
