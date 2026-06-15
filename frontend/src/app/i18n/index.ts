import i18n from 'i18next'
import LanguageDetector from 'i18next-browser-languagedetector'
import { initReactI18next } from 'react-i18next'
import { ru } from './ru'

i18n
  .use(LanguageDetector)
  .use(initReactI18next)
  .init({
    resources: { ru },
    fallbackLng: 'ru',
    lng: 'ru',
    interpolation: { escapeValue: false },
  })

export default i18n
