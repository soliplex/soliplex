# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**soliplex-ingester-ui** is a Svelte-based front-end application for interacting with REST APIs. This project uses Svelte 5 with the modern runes syntax and TypeScript. This application connects to a REST server located at http://127.0.0.1/api/v1. It has a specification file located at http://127.0.0.1:8000/openapi.json. Documentation for this application is located at ../soliplex_ingester/README.md. The user interface is intended to montor the status of workflows and interrogate workflow and parameter definitions. It should also display results from all endpoints in the stats group.

## Common Commands

**Development:**

- `npm install` - Install all dependencies
- `npm run dev` - Start development server (opens at http://localhost:5173)
- `npm run build` - Build for production
- `npm run preview` - Preview production build locally

**Code Quality:**

- `npm run check` - Run TypeScript and Svelte type checking
- `npm run check:watch` - Run type checking in watch mode
- `npm run lint` - Lint code with ESLint
- `npm run format` - Format code with Prettier

# Technical Requirements

- Svelte v5
- Tailwind CSS V4
- Accessibility (a11y) AA compliant
- Responsive design (mobile-first)
- Clean and maintainable code with re-usable Svelte components

Please read all the latest documentation for (Svelte Kit)[svelte.dev/llms.txt] and Tailwind CSS to ensure you are familiar with the latest features and best practices before implementing any new features or changes in these areas.

# Code style

- Use ES modules (import/export) syntax, not CommonJS (require)
- Destructure imports when possible (eg. import { foo } from 'bar')
- Each Svelte component should declare its own prop types using TypeScript within the same file
- Svelte component files should have constants declared outside the component function
- Use camelCase for variable and function names
- Use PascalCase for Svelte components
- Avoid use of inline styles, prefer Tailwind CSS classes
- Avoid using `any` type in Typescript or casting with as
- Declare constant values and objects using `const`
- Constant values that are objects, do not use CAPS for the variable name, use camelCase instead suffixed with 'Value'
- Event handlers should be named with the `handle` prefix (e.g. `handleClick`)
- Only write code comments when the code is not clear and keep it conscise, avoid commenting out code
- Avoid magic numbers and strings, use constants instead
- Each file should have line break at the end
- Try to limit components and modules up to 200 lines and split in to different components to manage complexity
- Typescript files should be camelCase e.g. myService.ts

# Workflow

- Be sure to run `npm run check` when you're done making a series of code changes
- Use `npm run format` whenever the format is not correct
- Prefer running single tests, and not the whole test suite, for performance

# Dependency management

- Ensure to find the latest version of a package before adding it
- Avoid using deprecated packages or APIs
