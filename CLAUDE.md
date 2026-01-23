# CLAUDE.md - QuestCraft WebAR Prototype

## Project Overview

**QuestCraft WebAR** is a browser-based Augmented Reality prototype application. It demonstrates a proof-of-concept for an AR treasure hunt experience using web technologies. When users point their camera at a HIRO marker, they see an animated 3D treasure chest with visual effects.

**Language**: Russian (all UI text and comments are in Russian)

## Project Structure

```
/home/user/webar/
├── CLAUDE.md          # This file - AI assistant guidelines
└── index.html         # Complete WebAR application (single-file architecture)
```

This is a **single-file application** - all HTML, CSS, and JavaScript are contained in `index.html`.

## Technology Stack

| Technology | Version | Purpose |
|------------|---------|---------|
| A-Frame | 1.4.0 | WebGL/VR framework for 3D scenes |
| AR.js | Latest | Marker-based AR detection |
| HTML5 | - | Page structure |
| CSS3 | - | Styling, animations |
| Vanilla JavaScript | ES6+ | UI interactions, event handling |

**External Dependencies** (loaded via CDN):
- `https://aframe.io/releases/1.4.0/aframe.min.js`
- `https://raw.githack.com/AR-js-org/AR.js/master/aframe/build/aframe-ar.js`

## Architecture

### File Structure (`index.html`)

| Section | Lines | Description |
|---------|-------|-------------|
| Head/Meta | 1-11 | Document setup, script imports |
| CSS Styles | 12-142 | UI component styles, animations |
| HTML Body | 144-166 | UI overlays (instructions, status, help) |
| A-Frame Scene | 167-295 | AR scene definition, 3D objects |
| JavaScript | 297-344 | Event handlers, UI logic |

### Key Components

**UI Elements**:
- Instructions overlay (`#instructions`) - Shows initial guidance, auto-hides after 5s
- Help button (`.help-btn`) - Top-right, shows/hides instructions
- Status panel (`.status-panel`) - Bottom center, shows marker detection state
- Marker info (`.marker-info`) - Appears when marker is detected

**AR Scene Elements**:
- `<a-marker preset="hiro">` - HIRO marker detection
- Treasure chest - Built from A-Frame primitives (`<a-box>`)
- Animated chest lid - Opens/closes animation
- Golden particles - Floating star effects
- Point light - Pulsing golden glow
- Rotating torus ring - Decorative orbit effect
- Text label - "Сокровище найдено!" (Treasure found!)

### AR Configuration

```html
arjs="sourceType: webcam; debugUIEnabled: false; detectionMode: mono_and_matrix; matrixCodeType: 3x3;"
```

**Marker tracking smoothing**:
```html
smooth="true"
smoothCount="10"
smoothTolerance="0.01"
smoothThreshold="5"
```

## Development Workflow

### Running Locally

No build process required. Serve the file via any HTTP server:

```bash
# Python 3
python -m http.server 8080

# Node.js (npx)
npx serve .

# PHP
php -S localhost:8080
```

**Important**: HTTPS is required for camera access on most browsers. For local development:
- Use `localhost` (browsers allow camera on localhost)
- Or use tools like `ngrok` for HTTPS tunneling

### Testing

1. Open the application in a browser
2. Allow camera permissions
3. Point camera at a [HIRO marker](https://raw.githubusercontent.com/AR-js-org/AR.js/master/data/images/hiro.png)
4. Verify 3D treasure chest appears and animates

### Debugging

Browser console shows:
- `QuestCraft WebAR Prototype загружен` - On load
- `Маркер HIRO найден!` - When marker detected
- `Маркер потерян` - When marker lost

## Code Conventions

### CSS
- Use rgba for backgrounds with transparency
- Animations defined via `@keyframes`
- BEM-like class naming (e.g., `.status-panel`, `.status-dot`)
- Z-index 1000 for overlay elements

### JavaScript
- Vanilla JS only, no frameworks
- DOM elements cached at top of script
- Event-driven architecture (markerFound/markerLost events)
- Feature detection before using APIs (e.g., `navigator.vibrate`)

### A-Frame/AR.js
- Use `animation` attribute for declarative animations
- Multiple animations on same element use `animation__name` suffix
- Primitives preferred over custom 3D models for this prototype
- Colors in hex format

## Common Tasks

### Adding New 3D Objects

Add objects inside the `<a-marker>` entity:

```html
<a-marker preset="hiro">
    <!-- Existing objects... -->

    <!-- New object -->
    <a-box
        position="0 1 0"
        color="#FF0000"
        animation="property: rotation; to: 0 360 0; dur: 2000; loop: true"
    ></a-box>
</a-marker>
```

### Changing the AR Marker

Replace `preset="hiro"` with a custom pattern:

```html
<a-marker type="pattern" url="path/to/pattern.patt">
```

### Adding New UI Components

1. Add CSS styles in the `<style>` section
2. Add HTML structure in the body (before `<a-scene>`)
3. Add JavaScript handlers at the bottom

### Modifying Animations

Animations use A-Frame's animation component format:
```html
animation="property: position; from: 0 0 0; to: 0 1 0; dur: 1000; loop: true"
```

## Browser Compatibility

| Browser | Support |
|---------|---------|
| Chrome (Android) | Full support |
| Safari (iOS 11+) | Full support |
| Firefox | Full support |
| Chrome (Desktop) | Full support (with webcam) |

**Requirements**:
- WebGL support
- getUserMedia API (camera access)
- Modern ES6+ JavaScript support

## Known Limitations

1. **Single marker only** - Currently supports only HIRO marker
2. **No offline mode** - Requires internet for CDN libraries
3. **Russian only** - No i18n implementation
4. **Monolithic structure** - All code in single file
5. **No custom 3D models** - Uses only A-Frame primitives

## Future Enhancement Ideas

- Multiple AR markers with different content
- Custom 3D model loading (GLTF/GLB)
- Internationalization support
- Progressive Web App (PWA) capabilities
- Modular code structure (separate HTML/CSS/JS)
- Build tooling (Vite/Webpack)
- Unit tests for JavaScript functions

## References

- [A-Frame Documentation](https://aframe.io/docs/)
- [AR.js Documentation](https://ar-js-org.github.io/AR.js-Docs/)
- [HIRO Marker Image](https://raw.githubusercontent.com/AR-js-org/AR.js/master/data/images/hiro.png)

## AI Assistant Guidelines

When working with this codebase:

1. **Preserve Russian language** - All user-facing text should remain in Russian unless translation is requested
2. **Maintain single-file structure** - Unless explicitly asked to modularize
3. **Test marker detection** - Any changes to the scene should be tested with the HIRO marker
4. **Keep CDN dependencies** - Don't convert to npm packages without explicit request
5. **Comment in Russian** - Match existing code comment language
6. **Preserve animations** - The visual effects are core to the experience
7. **Mobile-first approach** - This is primarily a mobile AR experience
